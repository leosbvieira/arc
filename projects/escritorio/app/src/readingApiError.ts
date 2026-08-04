export class ReadingApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ReadingApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function readingErrorDetail(error: unknown): string | null {
  return error instanceof ReadingApiError ? error.detail : null;
}
