# EAOptimizer

Repositório do projeto local `C:\Projetos\EAOptimizer`, consolidado para manter backend e frontend do produto no mesmo núcleo.

## Estrutura

- `ea_optimizer/backend/`: API Flask, engine quantitativa e persistência.
- `ea_optimizer/frontend/`: frontend React + TypeScript + Vite com dashboards e painéis de análise.
- `ea_optimizer/start_system.py`: inicialização do backend e instruções do frontend.

## Como começar

```bash
cd ea_optimizer/backend
pip install -r requirements.txt
cd ../frontend
npm install
cd ..
python start_system.py
```

## Observações

- O repositório usa `.gitignore` para evitar envio de dependências, caches e bancos locais.
- A estrutura foi consolidada para manter um único frontend oficial em `ea_optimizer/frontend`.
