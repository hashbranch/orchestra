defmodule SymphonyElixir.Workflow do
  @moduledoc """
  Loads structured workflow configuration from orchestra.yaml and prompt text from WORKFLOW.md.
  """

  alias SymphonyElixir.WorkflowStore

  @workflow_file_name "WORKFLOW.md"
  @config_file_name "orchestra.yaml"

  @spec workflow_file_path() :: Path.t()
  def workflow_file_path do
    Application.get_env(:symphony_elixir, :workflow_file_path) ||
      Path.join(File.cwd!(), @workflow_file_name)
  end

  @spec config_file_path() :: Path.t()
  def config_file_path do
    Application.get_env(:symphony_elixir, :workflow_config_file_path) ||
      config_file_path_for_workflow(workflow_file_path())
  end

  @spec set_workflow_file_path(Path.t()) :: :ok
  def set_workflow_file_path(path) when is_binary(path) do
    Application.put_env(:symphony_elixir, :workflow_file_path, path)
    maybe_reload_store()
    :ok
  end

  @spec clear_workflow_file_path() :: :ok
  def clear_workflow_file_path do
    Application.delete_env(:symphony_elixir, :workflow_file_path)
    maybe_reload_store()
    :ok
  end

  @spec set_config_file_path(Path.t()) :: :ok
  def set_config_file_path(path) when is_binary(path) do
    Application.put_env(:symphony_elixir, :workflow_config_file_path, path)
    maybe_reload_store()
    :ok
  end

  @spec clear_config_file_path() :: :ok
  def clear_config_file_path do
    Application.delete_env(:symphony_elixir, :workflow_config_file_path)
    maybe_reload_store()
    :ok
  end

  @type loaded_workflow :: %{
          config: map(),
          prompt: String.t(),
          prompt_template: String.t()
        }

  @spec current() :: {:ok, loaded_workflow()} | {:error, term()}
  def current do
    case Process.whereis(WorkflowStore) do
      pid when is_pid(pid) ->
        WorkflowStore.current()

      _ ->
        load()
    end
  end

  @spec load() :: {:ok, loaded_workflow()} | {:error, term()}
  def load do
    load(workflow_file_path())
  end

  @spec load(Path.t()) :: {:ok, loaded_workflow()} | {:error, term()}
  def load(path) when is_binary(path) do
    case File.read(path) do
      {:ok, content} ->
        parse(path, content)

      {:error, reason} ->
        {:error, {:missing_workflow_file, path, reason}}
    end
  end

  @spec current_stamp(Path.t()) :: {:ok, term()} | {:error, term()}
  def current_stamp(path) when is_binary(path) do
    config_path = effective_config_file_path(path)

    with {:ok, workflow_stamp} <- file_stamp(path),
         {:ok, config_stamp} <- optional_file_stamp(config_path) do
      {:ok, {workflow_stamp, config_path, config_stamp}}
    end
  end

  defp parse(path, content) do
    config_path = effective_config_file_path(path)
    {_front_matter_lines, prompt_lines} = split_front_matter(content)
    prompt = Enum.join(prompt_lines, "\n") |> String.trim()

    case load_config(content, config_path) do
      {:ok, config} ->
        {:ok,
         %{
           config: config,
           prompt: prompt,
           prompt_template: prompt
         }}

      {:error, :workflow_front_matter_not_a_map} ->
        {:error, :workflow_front_matter_not_a_map}

      {:error, :workflow_config_not_a_map} ->
        {:error, :workflow_config_not_a_map}

      {:error, reason} ->
        {:error, {:workflow_parse_error, reason}}
    end
  end

  defp load_config(content, config_path) do
    if File.exists?(config_path) do
      yaml_file_to_map(config_path, :workflow_config_not_a_map)
    else
      {front_matter_lines, _prompt_lines} = split_front_matter(content)
      front_matter_yaml_to_map(front_matter_lines)
    end
  end

  defp split_front_matter(content) do
    lines = String.split(content, ~r/\R/, trim: false)

    case lines do
      ["---" | tail] ->
        {front, rest} = Enum.split_while(tail, &(&1 != "---"))

        case rest do
          ["---" | prompt_lines] -> {front, prompt_lines}
          _ -> {front, []}
        end

      _ ->
        {[], lines}
    end
  end

  defp front_matter_yaml_to_map(lines) do
    yaml = Enum.join(lines, "\n")

    if String.trim(yaml) == "" do
      {:ok, %{}}
    else
      yaml_string_to_map(yaml, :workflow_front_matter_not_a_map)
    end
  end

  defp yaml_file_to_map(path, non_map_error) do
    case File.read(path) do
      {:ok, yaml} -> yaml_string_to_map(yaml, non_map_error)
      {:error, reason} -> {:error, {:missing_workflow_config_file, path, reason}}
    end
  end

  defp yaml_string_to_map(yaml, non_map_error) do
    case YamlElixir.read_from_string(yaml) do
      {:ok, decoded} when is_map(decoded) -> {:ok, decoded}
      {:ok, _} -> {:error, non_map_error}
      {:error, reason} -> {:error, reason}
    end
  end

  defp effective_config_file_path(workflow_path) do
    Application.get_env(:symphony_elixir, :workflow_config_file_path) ||
      config_file_path_for_workflow(workflow_path)
  end

  defp config_file_path_for_workflow(workflow_path) do
    workflow_path
    |> Path.dirname()
    |> Path.join(@config_file_name)
  end

  defp optional_file_stamp(path) when is_binary(path) do
    if File.exists?(path) do
      file_stamp(path)
    else
      {:ok, :missing}
    end
  end

  defp file_stamp(path) when is_binary(path) do
    with {:ok, stat} <- File.stat(path, time: :posix),
         {:ok, content} <- File.read(path) do
      {:ok, {stat.mtime, stat.size, :erlang.phash2(content)}}
    else
      {:error, reason} -> {:error, reason}
    end
  end

  defp maybe_reload_store do
    if Process.whereis(WorkflowStore) do
      _ = WorkflowStore.force_reload()
    end

    :ok
  end
end
