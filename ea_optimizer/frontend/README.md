# EAOptimizer Frontend

Frontend oficial do EA Configuration Optimizer, construído com React, TypeScript, Vite e Tailwind CSS.

## Variáveis de ambiente

Copie `.env.example` para `.env` e ajuste a URL da API quando necessário.

```bash
VITE_API_BASE_URL=http://localhost:5000
```

Em produção na Vercel, defina `VITE_API_BASE_URL` com a URL pública do backend.

## Executar localmente

```bash
npm install
npm run dev
```

A interface fica disponível em `http://localhost:5173`.

## Build

```bash
npm run build
npm run preview
```

## Estrutura

- `src/sections/`: painéis analíticos do dashboard
- `src/components/ui/`: componentes reutilizáveis
- `src/hooks/`: hooks utilitários
- `src/lib/`: helpers compartilhados
