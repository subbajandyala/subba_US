import axios from "axios";

export const api = axios.create({
  baseURL: typeof window !== "undefined" ? "" : "http://localhost:8000",
  timeout: 15_000,
});
