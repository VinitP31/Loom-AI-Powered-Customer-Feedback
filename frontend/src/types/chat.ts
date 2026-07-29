/**
 * POST /chat contract — mirrors backend/api/response_models.py's
 * ChatRequest/ChatResponse/ChatSourceOut exactly. RAG chat over persisted
 * tickets: scope="dashboard" searches one upload (snapshot_id required),
 * scope="all" searches every upload so far.
 */

export type ChatScope = "dashboard" | "all";

export interface ChatSource {
  ticket_id: string;
  snapshot_id: number;
  source_filename: string;
  similarity: number;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
}
