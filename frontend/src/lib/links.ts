/**
 * The "Back to the diagnosis" target comes from the URL, so it is untrusted. Only an internal
 * diagnosis path is honoured; anything else (another site, javascript:, //host) is dropped.
 */
export function backLink(from: string | null): string | null {
  return from && /^\/equipment\/[0-9a-f-]+(\?[\w=&%.-]*)?$/i.test(from) ? from : null;
}
