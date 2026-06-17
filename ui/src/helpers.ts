export function normalizeCitationLinks(text: string): string {
  return text.replace(
    /\[Fonte:\s*([^\]]+)\]/g,
    (_match: string, rawSources: string) => {
      const links = rawSources
        .split(";")
        .map((s: string) => s.trim())
        .filter(Boolean)
        .map((s: string) => s.replace(/[)\].,;]+$/g, ""))
        .filter((s: string) => /^https?:\/\//i.test(s))
        .map((url: string, index: number) => `[Fonte ${index + 1}](${url})`);
      return links.length ? links.join("; ") : "[sem fonte válida]";
    },
  );
}
