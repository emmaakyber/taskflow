import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App.jsx";
import * as api from "../api.js";

// The API module is mocked at its boundary: these tests cover the UI's data
// flow and states, not the network. api.js itself is a thin fetch wrapper.
vi.mock("../api.js", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    listTasks: vi.fn(),
    createTask: vi.fn(),
    completeTask: vi.fn(),
    updateTask: vi.fn(),
    deleteTask: vi.fn(),
    getStats: vi.fn(),
  };
});

const task = (overrides) => ({
  id: 1,
  title: "Write report",
  completed: false,
  created_at: "2026-10-09T16:00:00Z",
  completed_at: null,
  ...overrides,
});

function primeApi({ tasks = [], stats = { total: 0, completed: 0, pending: 0 } } = {}) {
  api.listTasks.mockResolvedValue(tasks);
  api.getStats.mockResolvedValue(stats);
}

beforeEach(() => vi.clearAllMocks());

describe("App", () => {
  it("renders tasks and server-provided stats", async () => {
    primeApi({
      tasks: [task(), task({ id: 2, title: "Ship it", completed: true, completed_at: "2026-10-09T16:05:00Z" })],
      stats: { total: 2, completed: 1, pending: 1 },
    });
    render(<App />);

    expect(await screen.findByText("Write report")).toBeInTheDocument();
    expect(screen.getByText("Ship it")).toBeInTheDocument();

    const stats = screen.getByLabelText("Task statistics");
    expect(within(stats).getByText("Total").previousSibling).toHaveTextContent("2");
    expect(within(stats).getByText("Completed").previousSibling).toHaveTextContent("1");
    expect(within(stats).getByText("Pending").previousSibling).toHaveTextContent("1");
  });

  it("shows the empty state when there are no tasks", async () => {
    primeApi();
    render(<App />);
    expect(await screen.findByText(/No tasks yet/)).toBeInTheDocument();
  });

  it("creates a task from the form, clears the input and refreshes", async () => {
    primeApi();
    api.createTask.mockResolvedValue(task({ title: "New task" }));
    render(<App />);
    await screen.findByText(/No tasks yet/);

    // After creation, the refetch returns the new task.
    primeApi({ tasks: [task({ title: "New task" })], stats: { total: 1, completed: 0, pending: 1 } });

    const input = screen.getByLabelText("New task title");
    await userEvent.type(input, "New task");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    expect(api.createTask).toHaveBeenCalledWith("New task");
    expect(await screen.findByText("New task")).toBeInTheDocument();
    expect(input).toHaveValue("");
  });

  it("shows the server's validation message inline when creation fails", async () => {
    primeApi();
    api.createTask.mockRejectedValue(new api.ApiError(400, "validation_error", "Field 'title' must not be empty."));
    render(<App />);
    await screen.findByText(/No tasks yet/);

    await userEvent.type(screen.getByLabelText("New task title"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Field 'title' must not be empty.");
  });

  it("completes a task and hides its Complete button afterwards", async () => {
    primeApi({ tasks: [task()], stats: { total: 1, completed: 0, pending: 1 } });
    api.completeTask.mockResolvedValue(task({ completed: true }));
    render(<App />);
    await screen.findByText("Write report");

    primeApi({ tasks: [task({ completed: true })], stats: { total: 1, completed: 1, pending: 0 } });
    await userEvent.click(screen.getByRole("button", { name: "Complete" }));

    expect(api.completeTask).toHaveBeenCalledWith(1);
    await waitFor(() => expect(screen.queryByRole("button", { name: "Complete" })).not.toBeInTheDocument());
    expect(screen.getByLabelText("Completed")).toBeInTheDocument();
  });

  it("undoes a completed task via PATCH and shows Complete again", async () => {
    primeApi({ tasks: [task({ completed: true, completed_at: "2026-10-09T16:05:00Z" })], stats: { total: 1, completed: 1, pending: 0 } });
    api.updateTask.mockResolvedValue(task());
    render(<App />);
    await screen.findByText("Write report");

    primeApi({ tasks: [task()], stats: { total: 1, completed: 0, pending: 1 } });
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));

    expect(api.updateTask).toHaveBeenCalledWith(1, { completed: false });
    expect(await screen.findByRole("button", { name: "Complete" })).toBeInTheDocument();
  });

  it("deletes a task and refreshes the list", async () => {
    primeApi({ tasks: [task()], stats: { total: 1, completed: 0, pending: 1 } });
    api.deleteTask.mockResolvedValue(null);
    render(<App />);
    await screen.findByText("Write report");

    primeApi();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(api.deleteTask).toHaveBeenCalledWith(1);
    expect(await screen.findByText(/No tasks yet/)).toBeInTheDocument();
  });

  it("requests the matching status when a filter tab is clicked", async () => {
    primeApi();
    render(<App />);
    await screen.findByText(/No tasks yet/);

    await userEvent.click(screen.getByRole("tab", { name: "Completed" }));

    await waitFor(() => expect(api.listTasks).toHaveBeenLastCalledWith("completed"));
    expect(await screen.findByText("No completed tasks.")).toBeInTheDocument();
  });

  it("shows a banner with a retry when loading fails", async () => {
    api.listTasks.mockRejectedValue(new api.ApiError(0, "network_error", "Could not reach the server."));
    api.getStats.mockRejectedValue(new api.ApiError(0, "network_error", "Could not reach the server."));
    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not reach the server.");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
