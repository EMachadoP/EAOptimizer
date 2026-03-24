# EA Configuration Optimizer v1.2

**Sistema Quantitativo de Otimização & Business Intelligence para Grid Trading**

---

## 📋 Visão Geral

O EA Configuration Optimizer é um sistema quantitativo completo para otimização de estratégias de Grid Trading, com foco em realismo estatístico e inteligência de contexto de mercado.

### Funcionalidades Principais (FR)

| Código | Funcionalidade | Descrição |
|--------|----------------|-----------|
| **FR-14** | Regime Detection | Classificação de regime via Hurst Exponent + ADX |
| **FR-15** | Survival Analysis | Kaplan-Meier para modelagem de time decay |
| **FR-16** | Robustness Mapping | Análise 3D de estabilidade paramétrica |
| FR-09 | Optimization Engine | Otimização com Ulcer Index e CVaR_95 |
| FR-12 | Slippage Model | Modelagem realista de slippage |
| FR-03 | Trade Reconstruction | Reconstrução de baskets + Basket_MAE |

---

## 🏗️ Arquitetura

```
ea_optimizer/
├── backend/
│   ├── api/
│   │   └── server.py          # Flask REST API
│   ├── core/
│   │   ├── trade_reconstruction.py   # FR-03
│   │   ├── regime_detection.py       # FR-14
│   │   ├── survival_analysis.py      # FR-15
│   │   ├── robustness_mapping.py     # FR-16
│   │   ├── optimization_engine.py    # FR-09
│   │   ├── slippage_model.py         # FR-12
│   │   └── mt5_importer.py           # FR-01/02
│   ├── models/
│   │   └── database.py        # SQLAlchemy models
│   └── requirements.txt
├── frontend/
│   └── (React + TypeScript + Tailwind)
├── ea_optimizer.db            # SQLite database
└── start_system.py            # System launcher
```

---

## 🚀 Instalação

### 1. Clone o repositório

```bash
cd ea_optimizer
```

### 2. Instale as dependências do backend

```bash
cd backend
pip install -r requirements.txt
cd ..
```

Observação importante:
- o pacote `MetaTrader5` agora faz parte das dependências oficiais
- a coleta direta do terminal MT5 exige Windows com o MetaTrader 5 aberto e logado

### 3. Instale as dependências do frontend

```bash
cd frontend
npm install
cd ..
```

---

## 🎯 Uso

### Fluxo recomendado com dados 100% reais

1. Abra o MetaTrader 5 no Windows e faça login na conta desejada
2. Garanta que o símbolo esteja visível no `Market Watch`
3. Rode a sincronização real:

```bash
run_real_mt5_sync.bat
```

Ou, se preferir o comando manual:

```bash
python sync_mt5_to_cloud.py --api-url https://eaoptimizer.onrender.com --symbol XAUUSDm --days 30 --mt5-path "C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
```

4. Depois abra o frontend e execute:
- `Regime Detection`
- `Survival Analysis`
- `Optimization`
- `Robustness`

### Regra de integridade dos dados

- a otimização em produção usa apenas `baskets históricos` e `trades reais`
- se não houver base real suficiente, o sistema para e mostra erro em vez de usar simulação
- isso garante coerência com backtests e validações do seu EA

### Iniciar o sistema completo

```bash
python start_system.py
```

Este comando irá:
1. Verificar dependências
2. Inicializar o banco de dados SQLite
3. Iniciar o backend Flask (porta 5000)
4. Fornecer instruções para iniciar o frontend

### Iniciar manualmente

**Backend:**
```bash
cd backend
python api/server.py
```

**Frontend:**
```bash
cd frontend
npm run dev
```

Acesse: http://localhost:5173

---

## 📊 Módulos

### FR-14: Regime Detection

Classifica o estado do mercado usando:
- **Hurst Exponent (R/S Analysis)**: H < 0.5 = Mean Reversion (favorável a grids)
- **ADX(14)**: ADX > 40 = Tendência forte (evitar)
- **EMA Slope**: Confirmação de direção

**Output**: Profit Matrix cruzando regimes vs métricas de performance

### FR-15: Survival Analysis

Aplica Kaplan-Meier para modelar:
- **S(t)**: Probabilidade de não atingir stop após t horas
- **h(t)**: Taxa instantânea de falha
- **Mediana de sobrevivência**: Tempo onde 50% dos baskets falham

**Output**: Time Stop suggestion baseado em dados

### FR-16: Robustness Mapping

Mapeia o landscape de parâmetros:
- **Zona Azul**: Configurações robustas (estabilidade ≥ 80%)
- **Zona Vermelha**: Picos de overfitting (alta performance, baixa estabilidade)

**Condição de Robustez**: Score(Grid±Δ, Mult±δ) > 0.8 × Score(ótimo) para 80% dos vizinhos

---

## 🔌 API Endpoints

### Health Check
```
GET /api/health
```

### Data Import
```
POST /api/import/market-data
POST /api/import/trades
```

### Regime Detection
```
POST /api/regime/analyze
GET  /api/regime/profit-matrix
```

### Survival Analysis
```
POST /api/survival/analyze
```

### Robustness Mapping
```
POST /api/robustness/analyze
GET  /api/robustness/surface-data
```

### Optimization
```
POST /api/optimization/run
GET  /api/optimization/results
```

### Dashboard
```
GET /api/dashboard/summary
```

---

## 📁 Estrutura de Dados

### Tabelas Principais

| Tabela | Descrição |
|--------|-----------|
| `market_data` | OHLCV + indicadores (ATR, ADX, Hurst) |
| `trades` | Trades individuais do EA |
| `grid_sequences` | Baskets completos com métricas |
| `regime_analysis` | Classificação de regime por timestamp |
| `survival_curves` | Curvas Kaplan-Meier |
| `robustness_landscape` | Scores de estabilidade |
| `optimization_results` | Resultados de otimização |

---

## 🧪 Testes

### Executar testes unitários

```bash
cd backend
pytest tests/
```

### Validar com dados reais

1. Abra o MT5 no Windows
2. Rode `run_real_mt5_sync.bat` ou `sync_mt5_to_cloud.py`
3. Confira no dashboard se `Market Data`, `Trades` e `Baskets` foram populados
4. Execute análises nos painéis específicos
5. Rode a otimização sabendo que o motor trabalha apenas com base real do EA

---

## 📈 Roadmap de Implementação

### Fase 1: Core & Data Foundation (Semanas 1-2) ✅
- [x] Pipeline de importação MT5
- [x] Trade Reconstruction Engine
- [x] Basket_MAE calculation
- [x] Look-ahead Bias Auditor

### Fase 2: Realismo & Risco (Semanas 3-4) ✅
- [x] Slippage Modeling
- [x] Optimization Engine (Ulcer, CVaR)

### Fase 3: Business Intelligence (Semanas 5-6) ✅
- [x] Regime Detection (Hurst + ADX)
- [x] Survival Analysis (Kaplan-Meier)
- [x] Robustness Mapping (3D Surface)
- [x] Dashboard Interativo

---

## 🛠️ Tecnologias

### Backend
- **Python 3.9+**
- **Flask**: Web framework
- **SQLAlchemy**: ORM
- **Pandas/NumPy/SciPy**: Análise quantitativa
- **MetaTrader5**: Integração direta com terminal real

### Frontend
- **React 18**
- **TypeScript**
- **Tailwind CSS**
- **shadcn/ui**: Componentes
- **Recharts**: Visualizações
- **Plotly**: Gráficos 3D

---

## 📚 Referências

### Hurst Exponent
- Mandelbrot, B. (1972). "Statistical Methodology for Nonperiodic Cycles"

### Kaplan-Meier Estimator
- Kaplan, E.L. & Meier, P. (1958). "Nonparametric Estimation from Incomplete Observations"

### Ulcer Index
- Peter Martin (1987). "The Investor's Guide to Fidelity Funds"

### CVaR
- Rockafellar, R.T. & Uryasev, S. (2000). "Optimization of Conditional Value-at-Risk"

---

## 📝 Licença

Este projeto é proprietário e confidencial.

---

## 👥 Contato

Para suporte ou dúvidas, consulte a documentação técnica do PRD 1.2.

**Versão**: 1.2 FINAL  
**Data**: 23/03/2026  
**Status**: Pronto para Desenvolvimento
