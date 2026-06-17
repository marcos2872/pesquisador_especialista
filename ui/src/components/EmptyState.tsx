import { Stack, Text } from '@mantine/core';

export function EmptyState() {
  return (
    <Stack align="center" gap="md" p="xl">
      <Text size="48px" style={{ opacity: 0.3 }}>🔬</Text>
      <Text fw={600} size="md">Nenhum relatório gerado</Text>
      <Text size="sm" c="dimmed" ta="center">
        Informe um tema de pesquisa e clique em &quot;Gerar pesquisa&quot; para começar.
      </Text>
    </Stack>
  );
}
