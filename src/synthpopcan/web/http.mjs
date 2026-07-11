export async function fetchJson(url, options = undefined) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = `Request returned HTTP ${response.status}`;
    try {
      const payload = await response.json();
      detail = payload.error ?? detail;
    } catch {
      // Keep the HTTP status message when the response is not JSON.
    }
    throw new Error(detail);
  }
  return response.json();
}
