defmodule SymphonyElixir.ClaudeCode do
  @moduledoc false

  require Logger

  alias SymphonyElixir.{Config, PathSafety, SSH}

  @port_line_bytes 1_048_576

  @spec run(Path.t(), String.t(), map(), map(), keyword()) :: {:ok, map()} | {:error, term()}
  def run(workspace, prompt, issue, runtime, opts \\ [])
      when is_binary(workspace) and is_binary(prompt) and is_map(runtime) do
    on_message = Keyword.get(opts, :on_message, &default_on_message/1)
    worker_host = Keyword.get(opts, :worker_host)

    with {:ok, expanded_workspace} <- validate_workspace_cwd(workspace, worker_host),
         {:ok, port} <- start_port(expanded_workspace, prompt, runtime, worker_host) do
      metadata = port_metadata(port, runtime, worker_host)
      session_id = "claude-#{System.unique_integer([:positive])}"

      Logger.info("Claude Code session started for #{issue_context(issue)} session_id=#{session_id}")
      emit_message(on_message, :session_started, %{session_id: session_id}, metadata)

      case await_completion(port, on_message, metadata, Config.settings!().codex.turn_timeout_ms, [], "") do
        {:ok, result} ->
          Logger.info("Claude Code session completed for #{issue_context(issue)} session_id=#{session_id}")
          emit_message(on_message, :turn_completed, %{session_id: session_id}, metadata)

          {:ok, %{result: result, session_id: session_id}}

        {:error, reason} ->
          Logger.warning("Claude Code session ended with error for #{issue_context(issue)} session_id=#{session_id}: #{inspect(reason)}")
          emit_message(on_message, :turn_ended_with_error, %{session_id: session_id, reason: reason}, metadata)

          {:error, reason}
      end
    end
  end

  defp validate_workspace_cwd(workspace, nil) do
    expanded_workspace = Path.expand(workspace)
    expanded_root = Path.expand(Config.settings!().workspace.root)
    expanded_root_prefix = expanded_root <> "/"

    with {:ok, canonical_workspace} <- PathSafety.canonicalize(expanded_workspace),
         {:ok, canonical_root} <- PathSafety.canonicalize(expanded_root) do
      canonical_root_prefix = canonical_root <> "/"

      cond do
        canonical_workspace == canonical_root ->
          {:error, {:invalid_workspace_cwd, :workspace_root, canonical_workspace}}

        String.starts_with?(canonical_workspace <> "/", canonical_root_prefix) ->
          {:ok, canonical_workspace}

        String.starts_with?(expanded_workspace <> "/", expanded_root_prefix) ->
          {:error, {:invalid_workspace_cwd, :symlink_escape, expanded_workspace, canonical_root}}

        true ->
          {:error, {:invalid_workspace_cwd, :outside_workspace_root, canonical_workspace, canonical_root}}
      end
    else
      {:error, {:path_canonicalize_failed, path, reason}} ->
        {:error, {:invalid_workspace_cwd, :path_unreadable, path, reason}}
    end
  end

  defp validate_workspace_cwd(workspace, worker_host) when is_binary(worker_host) do
    cond do
      String.trim(workspace) == "" ->
        {:error, {:invalid_workspace_cwd, :empty_remote_workspace, worker_host}}

      String.contains?(workspace, ["\n", "\r", <<0>>]) ->
        {:error, {:invalid_workspace_cwd, :invalid_remote_workspace, worker_host, workspace}}

      true ->
        {:ok, workspace}
    end
  end

  defp start_port(workspace, prompt, runtime, nil) do
    executable = System.find_executable("bash")

    if is_nil(executable) do
      {:error, :bash_not_found}
    else
      port =
        Port.open(
          {:spawn_executable, String.to_charlist(executable)},
          [
            :binary,
            :exit_status,
            :stderr_to_stdout,
            args: [~c"-lc", String.to_charlist(command_line(runtime, prompt))],
            cd: String.to_charlist(workspace),
            line: @port_line_bytes
          ]
        )

      {:ok, port}
    end
  end

  defp start_port(workspace, prompt, runtime, worker_host) when is_binary(worker_host) do
    remote_command =
      [
        "cd #{shell_escape(workspace)}",
        "exec #{command_line(runtime, prompt)}"
      ]
      |> Enum.join(" && ")

    SSH.start_port(worker_host, remote_command, line: @port_line_bytes)
  end

  defp command_line(runtime, prompt) do
    args =
      []
      |> append_flag("--print", runtime_value(runtime, :print))
      |> append_flag("--bare", runtime_value(runtime, :bare))
      |> append_value("--output-format", runtime_value(runtime, :output_format))
      |> append_value("--permission-mode", runtime_value(runtime, :permission_mode))
      |> append_value("--model", runtime_value(runtime, :model))
      |> append_value("--effort", runtime_value(runtime, :effort))
      |> Kernel.++(["-p", prompt])

    runtime_command(runtime) <> " " <> Enum.map_join(args, " ", &shell_escape/1)
  end

  defp append_flag(args, flag, true), do: args ++ [flag]
  defp append_flag(args, _flag, _value), do: args

  defp append_value(args, _flag, value) when value in [nil, ""], do: args
  defp append_value(args, flag, value), do: args ++ [flag, to_string(value)]

  defp runtime_command(runtime) do
    case runtime_value(runtime, :command) do
      command when is_binary(command) and command != "" -> command
      _ -> "claude"
    end
  end

  defp await_completion(port, on_message, metadata, timeout_ms, lines, pending_line) do
    receive do
      {^port, {:data, {:eol, chunk}}} ->
        line = pending_line <> to_string(chunk)
        emit_stream_line(on_message, line, metadata)
        await_completion(port, on_message, metadata, timeout_ms, [line | lines], "")

      {^port, {:data, {:noeol, chunk}}} ->
        await_completion(port, on_message, metadata, timeout_ms, lines, pending_line <> to_string(chunk))

      {^port, {:exit_status, 0}} ->
        {:ok, Enum.reverse(lines)}

      {^port, {:exit_status, status}} ->
        {:error, {:port_exit, status, Enum.reverse(lines)}}
    after
      timeout_ms ->
        Port.close(port)
        {:error, :turn_timeout}
    end
  end

  defp emit_stream_line(on_message, line, metadata) do
    payload =
      case Jason.decode(line) do
        {:ok, decoded} when is_map(decoded) -> decoded
        {:ok, decoded} -> %{"value" => decoded}
        {:error, _reason} -> %{"text" => line}
      end

    method =
      case Map.get(payload, "type") || Map.get(payload, :type) || Map.get(payload, "method") || Map.get(payload, :method) do
        value when is_binary(value) and value != "" -> "claude/event/#{value}"
        _ -> "claude/event/output"
      end

    emit_message(
      on_message,
      :notification,
      %{payload: %{"method" => method, "params" => payload}, raw: line},
      metadata
    )
  end

  defp emit_message(on_message, event, message, metadata) do
    message =
      metadata
      |> Map.merge(message)
      |> Map.put(:event, event)
      |> Map.put(:timestamp, DateTime.utc_now())

    on_message.(message)
  end

  defp port_metadata(port, runtime, worker_host) do
    base_metadata =
      case :erlang.port_info(port, :os_pid) do
        {:os_pid, os_pid} -> %{claude_code_pid: to_string(os_pid)}
        _ -> %{}
      end
      |> Map.put(:runtime_name, runtime_value(runtime, :name) || "claude")
      |> Map.put(:runtime_kind, "claude_code")

    case worker_host do
      host when is_binary(host) -> Map.put(base_metadata, :worker_host, host)
      _ -> base_metadata
    end
  end

  defp runtime_value(runtime, key) when is_map(runtime), do: Map.get(runtime, key) || Map.get(runtime, to_string(key))
  defp runtime_value(_runtime, _key), do: nil

  defp shell_escape(value) when is_binary(value) do
    "'" <> String.replace(value, "'", "'\"'\"'") <> "'"
  end

  defp default_on_message(_message), do: :ok

  defp issue_context(%{id: issue_id, identifier: identifier}) do
    "issue_id=#{issue_id} issue_identifier=#{identifier}"
  end
end
