// Game state types - aligned with backend aisim.shared.models (see §6 frontend WS protocol).

export type AgentStatus = "booting" | "initializing" | "ready" | "working" | "offline";

export interface AgentState {
  agent_id: string;
  name: string;
  role: string;
  department: string;
  status: AgentStatus;
  mood: number; // -1 ~ 1
  energy: number; // 0 ~ 100
  x: number;
  y: number;
  recent: { content: string; type: string }[]; // recent thoughts/actions
}

export interface EconomyState {
  capital: number;
  monthly_burn: number;
  revenue: number;
  bankrupt: boolean;
}

export interface GameSnapshot {
  company: string;
  economy: EconomyState;
  tick: number;
  agents: AgentState[];
  tasks: Task[];
  skills: Skill[];
}

export type TaskStatus = "pending" | "in_progress" | "done" | "blocked";

export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  assignee: string;
  assignee_role: string;
  project: string;
  priority: string;
  created_by: string;
  created_tick: number;
  completed_tick: number;
  completed_by: string;
  result: string;
}

export type SkillLevel = "company" | "department" | "role" | "personal";

export interface Skill {
  id: string;
  name: string;
  category: string;
  level: SkillLevel;
  scope: string[];
  description: string;
  prompt_injection: string;
  created_by: string;
  status: string;
  usage_count: number;
}

export type LogKind =
  | "message"
  | "action"
  | "created"
  | "meeting"
  | "task"
  | "system";

export type LogEntry = {
  ts: number;
  text: string;
  kind: LogKind;
};

// Hub -> frontend render events (see §6). Fields align with backend hub.snapshot_event / emit_frontend.
export type FrontendEvent =
  | { type: "agent_message"; sender: string; content: string }
  | { type: "agent_action"; agent: string; action: string; target?: string }
  | { type: "agent_created"; agent_id: string; name: string; role: string }
  | { type: "meeting_start"; participants: string[] }
  | { type: "meeting_minutes"; topic: string; minutes: string; by: string; participants: string[] }
  | { type: "task_created"; task_id: string; title: string; assignee_role: string; assignee: string }
  | { type: "task_completed"; task_id: string; title: string; result: string; by: string }
  | {
      type: "state_snapshot";
      tick: number;
      company: string;
      agents: AgentState[];
      tasks: Task[];
      skills: Skill[];
      bank: number;
      economy: EconomyState;
    };
