import { useState, useEffect } from "react";
import {
  AppShell,
  Badge,
  Button,
  Card,
  Container,
  Group,
  MantineProvider,
  Stack,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { theme } from "./theme";
import { normalizeCitationLinks } from "./helpers";
import { EmptyState } from "./components/EmptyState";
import { AppNavbar } from "./components/AppNavbar";
import { MarkdownRenderer } from "./components/MarkdownRenderer";
import type { HistoryItem } from "./types";
import "./App.css";

const ASSETS = {
  brand: "/assets/senai-brand.svg",
  logoReduction: "/assets/logo-light-reduction.png",
  logoFull: "/assets/logo-full.svg",
};

function badgeColor(type: string): string {
  switch (type) {
    case "success":
      return "green";
    case "error":
      return "red";
    default:
      return "gray";
  }
}

export default function App() {
  const [topic, setTopic] = useState("");
  const [report, setReport] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [status, setStatus] = useState({ text: "Pronto.", type: "neutral" });
  const [sidebarActive, setSidebarActive] = useState("nova-pesquisa");
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);

  async function loadHistory() {
    try {
      const resp = await fetch("/api/history");
      const data = await resp.json();
      setHistoryItems(data.researches || []);
    } catch {
      /* History is non-critical */
    }
  }

  async function loadResearchFromHistory(id: number) {
    try {
      const resp = await fetch(`/api/history/${id}`);
      if (!resp.ok) return;
      const data = await resp.json();
      setTopic(data.topic || "");
      setReport(data.report || "");
      setSidebarActive("nova-pesquisa");
      setStatus({ text: "Pesquisa carregada.", type: "neutral" });
    } catch {
      /* Silently ignore */
    }
  }

  useEffect(() => {
    loadHistory();
  }, []);
  useEffect(() => {
    if (!isRunning && report) loadHistory();
  }, [isRunning]);

  async function runResearch() {
    const topicValue = topic.trim();
    if (!topicValue) {
      setStatus({ text: "Informe um tópico de pesquisa.", type: "error" });
      return;
    }
    setIsRunning(true);
    setStatus({ text: "Gerando relatório...", type: "neutral" });
    setReport("");
    try {
      const response = await fetch("/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: topicValue }),
      });
      const data = await response.json();
      if (!response.ok)
        throw new Error(data.error || "Falha ao gerar pesquisa.");
      const markdown = data.report || "Sem conteúdo retornado.";
      setReport(markdown);
      setStatus({ text: "Pesquisa concluída.", type: "success" });
    } catch (error: any) {
      setReport("");
      setStatus({ text: `Erro: ${error.message}`, type: "error" });
    } finally {
      setIsRunning(false);
    }
  }

  async function copyMarkdown() {
    if (!report) {
      setStatus({ text: "Nada para copiar ainda.", type: "neutral" });
      return;
    }
    try {
      await navigator.clipboard.writeText(report);
      setStatus({ text: "Markdown copiado.", type: "success" });
    } catch {
      setStatus({ text: "Falha ao copiar.", type: "error" });
    }
  }

  const hasReport = report.length > 0;

  return (
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <AppShell
        header={{ height: 72 }}
        navbar={{ width: 247, breakpoint: "sm", collapsed: { mobile: true } }}
        padding="lg"
      >
        <AppShell.Header
          style={{ background: "#121212", borderBottom: "1px solid #333333" }}
        >
          <Container size="xl" h="100%" px="lg">
            <Group h="100%" justify="space-between" align="center">
              <img
                src={ASSETS.brand}
                alt="SENAI-SP Distrito Tecnológico"
                className="logo-header"
              />
              <Group gap="xs" visibleFrom="sm">
                <Text size="sm" c="#5E6267" fw={500}>
                  INOVAÇÃO E INDÚSTRIA CONECTADAS
                </Text>
              </Group>
            </Group>
          </Container>
        </AppShell.Header>

        <AppNavbar
          active={sidebarActive}
          onNavigate={setSidebarActive}
          historyItems={historyItems}
          onSelectHistory={loadResearchFromHistory}
        />

        <AppShell.Main style={{ background: "#121212" }}>
          <Container size="xl" py="xl">
            <Stack gap="lg">
              {/* Breadcrumb */}
              <Group gap="xs">
                <Text size="sm" c="#5E6267">
                  Pesquisas
                </Text>
                <Text size="sm" c="#5E6267">
                  ›
                </Text>
                <Text size="sm" fw={600} c="#ffffff">
                  Nova Pesquisa
                </Text>
              </Group>

              {/* Input Card */}
              <Card
                withBorder
                radius="md"
                style={{ background: "#232323", borderColor: "#333333" }}
              >
                <Stack gap="md">
                  <Title order={3} size="h4">
                    Nova pesquisa
                  </Title>
                  <Text size="sm" c="#9b9b9b">
                    Informe um tema de pesquisa. O sistema retorna estado da
                    arte, patentes, comparação técnica, lacunas e conclusão com
                    fonte por trecho.
                  </Text>
                  <Textarea
                    label="TÓPICO DA PESQUISA"
                    required
                    value={topic}
                    onChange={(event) => setTopic(event.currentTarget.value)}
                    placeholder="Ex.: nanocompósitos polímero/grafeno para aplicação automotiva"
                    minRows={8}
                    autosize
                    styles={{
                      label: {
                        fontSize: 12,
                        fontWeight: 700,
                        color: "#fcfcfc",
                      },
                      input: {
                        height: 44,
                        borderColor: "#333333",
                        "&:focus": { borderColor: "#D72042" },
                      },
                    }}
                  />
                  <Group justify="space-between" align="center" wrap="wrap">
                    <Button
                      variant="filled"
                      color="distrito"
                      size="md"
                      radius="md"
                      loading={isRunning}
                      disabled={isRunning}
                      onClick={runResearch}
                      style={{ "&:hover": { opacity: 0.85 } }}
                    >
                      Gerar pesquisa
                    </Button>
                    <Badge
                      color={badgeColor(status.type)}
                      variant="light"
                      size="sm"
                    >
                      {status.text}
                    </Badge>
                  </Group>
                </Stack>
              </Card>

              {/* Output Card */}
              <Card
                withBorder
                radius="md"
                style={{ background: "#232323", borderColor: "#333333" }}
              >
                <Stack gap="md">
                  <Group justify="space-between" align="center">
                    <Title order={3} size="h4">
                      Resultado
                    </Title>
                    <Button
                      variant="outline"
                      color="distrito"
                      size="sm"
                      radius="md"
                      onClick={copyMarkdown}
                      disabled={isRunning || !hasReport}
                    >
                      Copiar markdown
                    </Button>
                  </Group>
                  {hasReport ? (
                    <Card.Section
                      style={{
                        background: "#2e2e2e",
                        border: "1px solid #333333",
                      }}
                    >
                      <div id="report-output">
                        <MarkdownRenderer
                          content={normalizeCitationLinks(report)}
                        />
                      </div>
                    </Card.Section>
                  ) : (
                    <EmptyState />
                  )}
                </Stack>
              </Card>
            </Stack>
          </Container>
        </AppShell.Main>
      </AppShell>
    </MantineProvider>
  );
}
