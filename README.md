# EAOptimizer

Repositório do projeto local `C:\Projetos\EAOptimizer`, com os artefatos atuais do aplicativo e da solução quantitativa para otimização de EAs.

## Estrutura

- `app/`: frontend React + TypeScript + Vite com dashboards e painéis de análise.
- `ea_optimizer/`: solução principal com backend em Python/Flask e frontend dedicado.

## Como começar

### Frontend em `app`

```bash
cd app
npm install
npm run dev
```

### Sistema em `ea_optimizer`

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
- Os READMEs internos de `app/` e `ea_optimizer/` mantêm os detalhes específicos de cada módulo.
