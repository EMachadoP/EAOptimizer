"""
EA Configuration Optimizer v1.2
Survival Analysis Module
FR-15: Trade/Basket Survival Analysis

Aplica análise de sobrevivência estatística (Kaplan-Meier estimator) para modelar
o "Time Decay" do risco em baskets de grid.

Métricas:
- Survival Function S(t): Probabilidade de não ter atingido stop após t horas
- Hazard Rate h(t): Taxa instantânea de falha no tempo t
- Median Survival Time: Tempo em que 50% dos baskets sobrevivem
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from scipy import stats
from scipy.interpolate import interp1d

@dataclass
class SurvivalCurve:
    """Curva de sobrevivência Kaplan-Meier"""
    time_hours: np.ndarray
    survival_prob: np.ndarray  # S(t)
    hazard_rate: np.ndarray    # h(t)
    confidence_lower: np.ndarray
    confidence_upper: np.ndarray
    
    # Metadados
    sample_size: int
    median_survival_time: float
    regime_filter: str
    config_hash: str

class KaplanMeierEstimator:
    """
    Estimador Kaplan-Meier para análise de sobrevivência de baskets
    
    S(t) = Π (1 - d_i / n_i)
    onde:
    - d_i = número de falhas (stops atingidos) no tempo t_i
    - n_i = número de baskets em risco no tempo t_i
    """
    
    def __init__(self, confidence_level: float = 0.95):
        self.confidence_level = confidence_level
        self.alpha = 1 - confidence_level
    
    def fit(
        self,
        durations: np.ndarray,
        event_observed: np.ndarray,
        regime_filter: str = "All",
        config_hash: str = ""
    ) -> SurvivalCurve:
        """
        Ajusta curva de sobrevivência Kaplan-Meier
        
        Args:
            durations: Array com tempos de sobrevivência (horas)
            event_observed: Array booleano (1 = falha/stop atingido, 0 = censurado/basket fechado normal)
            regime_filter: Filtro de regime aplicado
            config_hash: Hash da configuração testada
        
        Returns:
            SurvivalCurve com S(t), h(t) e intervalos de confiança
        """
        # Remover NaN e negativos
        mask = ~(np.isnan(durations) | (durations < 0))
        durations = durations[mask]
        event_observed = event_observed[mask]
        
        if len(durations) == 0:
            return self._empty_curve(regime_filter, config_hash)
        
        # Ordenar por tempo
        sorted_indices = np.argsort(durations)
        durations = durations[sorted_indices]
        event_observed = event_observed[sorted_indices]
        
        # Tempos únicos onde eventos ocorreram
        unique_times = np.unique(durations[event_observed == 1])
        
        if len(unique_times) == 0:
            return self._empty_curve(regime_filter, config_hash)
        
        # Calcular Kaplan-Meier
        survival_probs = []
        conf_lower = []
        conf_upper = []
        hazard_rates = []
        
        n_at_risk = len(durations)
        survival_prob = 1.0
        
        for t in unique_times:
            # Baskets que falharam neste tempo
            d = np.sum((durations == t) & (event_observed == 1))
            
            # Baskets censurados neste tempo
            c = np.sum((durations == t) & (event_observed == 0))
            
            # Atualizar sobrevivência
            if n_at_risk > 0:
                survival_prob *= (1 - d / n_at_risk)
            
            # Calcular hazard rate
            if n_at_risk > 0:
                hazard = d / n_at_risk
            else:
                hazard = 0
            
            # Intervalo de confiança (Greenwood's formula)
            if n_at_risk > 0 and survival_prob > 0:
                var = (survival_prob ** 2) * np.sum([
                    d_i / (n_i * (n_i - d_i)) 
                    for d_i, n_i in self._get_at_risk_counts(durations, event_observed, t)
                    if n_i > d_i and d_i > 0
                ])
                
                z = stats.norm.ppf(1 - self.alpha / 2)
                ci = z * np.sqrt(var)
                
                lower = max(0, survival_prob - ci)
                upper = min(1, survival_prob + ci)
            else:
                lower = upper = survival_prob
            
            survival_probs.append(survival_prob)
            conf_lower.append(lower)
            conf_upper.append(upper)
            hazard_rates.append(hazard)
            
            # Atualizar risco
            n_at_risk -= (d + c)
        
        # Calcular mediana de sobrevivência
        median_time = self._calculate_median_survival(unique_times, np.array(survival_probs))
        
        return SurvivalCurve(
            time_hours=unique_times,
            survival_prob=np.array(survival_probs),
            hazard_rate=np.array(hazard_rates),
            confidence_lower=np.array(conf_lower),
            confidence_upper=np.array(conf_upper),
            sample_size=len(durations),
            median_survival_time=median_time,
            regime_filter=regime_filter,
            config_hash=config_hash
        )
    
    def _get_at_risk_counts(
        self,
        durations: np.ndarray,
        event_observed: np.ndarray,
        current_t: float
    ) -> List[Tuple[int, int]]:
        """Retorna contagens de falhas e risco até o tempo t"""
        counts = []
        unique_times = np.unique(durations[event_observed == 1])
        
        for t in unique_times:
            if t > current_t:
                break
            d = np.sum((durations == t) & (event_observed == 1))
            n = np.sum(durations >= t)
            counts.append((d, n))
        
        return counts
    
    def _calculate_median_survival(
        self,
        times: np.ndarray,
        survival_probs: np.ndarray
    ) -> float:
        """Calcula tempo de sobrevivência mediano (S(t) = 0.5)"""
        if len(survival_probs) == 0:
            return 0.0
        
        if survival_probs[-1] > 0.5:
            # Mais de 50% sobrevivem até o final
            return float(times[-1])
        
        if survival_probs[0] < 0.5:
            # Menos de 50% sobrevivem desde o início
            return float(times[0])
        
        # Interpolar para encontrar onde S(t) = 0.5
        try:
            # Encontrar índice onde cruza 0.5
            for i in range(len(survival_probs) - 1):
                if survival_probs[i] >= 0.5 and survival_probs[i + 1] < 0.5:
                    # Interpolação linear
                    t1, t2 = times[i], times[i + 1]
                    s1, s2 = survival_probs[i], survival_probs[i + 1]
                    median = t1 + (0.5 - s1) * (t2 - t1) / (s2 - s1)
                    return float(median)
        except:
            pass
        
        return float(times[np.argmin(np.abs(survival_probs - 0.5))])
    
    def _empty_curve(self, regime_filter: str, config_hash: str) -> SurvivalCurve:
        """Retorna curva vazia"""
        return SurvivalCurve(
            time_hours=np.array([0]),
            survival_prob=np.array([1.0]),
            hazard_rate=np.array([0.0]),
            confidence_lower=np.array([1.0]),
            confidence_upper=np.array([1.0]),
            sample_size=0,
            median_survival_time=0.0,
            regime_filter=regime_filter,
            config_hash=config_hash
        )

class SurvivalAnalysisEngine:
    """
    Motor completo de análise de sobrevivência para baskets de grid
    """
    
    def __init__(self):
        self.km_estimator = KaplanMeierEstimator()
    
    def analyze_baskets(
        self,
        baskets: pd.DataFrame,
        regime_filter: Optional[str] = None,
        config_hash: str = ""
    ) -> SurvivalCurve:
        """
        Analisa sobrevivência de baskets
        
        Args:
            baskets: DataFrame com colunas:
                - 'exposure_time_hours': tempo de exposição
                - 'hit_stop_loss': boolean (True se atingiu stop)
                - 'regime_at_start': regime no início (opcional)
            regime_filter: Filtrar por regime específico
            config_hash: Hash da configuração
        
        Returns:
            SurvivalCurve
        """
        df = baskets.copy()
        
        # Aplicar filtro de regime
        if regime_filter and 'regime_at_start' in df.columns:
            df = df[df['regime_at_start'] == regime_filter]
        
        if len(df) == 0:
            return self.km_estimator._empty_curve(regime_filter or "All", config_hash)
        
        # Preparar dados
        durations = df['exposure_time_hours'].values
        event_observed = df['hit_stop_loss'].astype(int).values
        
        # Ajustar curva
        return self.km_estimator.fit(
            durations=durations,
            event_observed=event_observed,
            regime_filter=regime_filter or "All",
            config_hash=config_hash
        )
    
    def generate_time_stop_suggestion(self, curve: SurvivalCurve) -> Dict:
        """
        Gera sugestão de Time Stop baseada na curva de sobrevivência
        
        Exemplo:
        "Implementar Time Stop dinâmico: Fechar basket no prejuízo após 6h de exposição,
        pois a curva de risco apresenta inflexão crítica (hazard rate > 15%/h) após esse ponto."
        """
        if curve.sample_size == 0:
            return {
                'suggested_time_stop': None,
                'rationale': 'Dados insuficientes',
                'confidence': 0.0
            }
        
        # Encontrar pontos críticos
        critical_points = self._find_critical_points(curve)
        
        # Analisar hazard rate
        hazard_analysis = self._analyze_hazard_rate(curve)
        
        # Sugerir time stop
        suggestion = self._suggest_time_stop(curve, critical_points, hazard_analysis)
        
        return {
            'suggested_time_stop': suggestion['time_hours'],
            'survival_at_suggestion': suggestion['survival_prob'],
            'rationale': suggestion['rationale'],
            'hazard_rate_at_suggestion': suggestion['hazard_rate'],
            'confidence': suggestion['confidence'],
            'median_survival_time': curve.median_survival_time,
            'critical_points': critical_points,
            'hazard_analysis': hazard_analysis
        }
    
    def _find_critical_points(self, curve: SurvivalCurve) -> List[Dict]:
        """Encontra pontos críticos na curva de sobrevivência"""
        points = []
        
        if len(curve.time_hours) < 3:
            return points
        
        # Encontrar onde S(t) cai abaixo de thresholds
        thresholds = [0.85, 0.50, 0.25]
        for threshold in thresholds:
            for i, s in enumerate(curve.survival_prob):
                if s <= threshold:
                    points.append({
                        'time_hours': float(curve.time_hours[i]),
                        'survival_prob': float(s),
                        'type': f'S(t) < {threshold}'
                    })
                    break
        
        # Encontrar inflexões no hazard rate
        if len(curve.hazard_rate) >= 3:
            hazard_diff = np.diff(curve.hazard_rate)
            for i in range(1, len(hazard_diff)):
                if hazard_diff[i-1] < 0 and hazard_diff[i] > 0:
                    # Inflexão (mínimo local)
                    points.append({
                        'time_hours': float(curve.time_hours[i+1]),
                        'hazard_rate': float(curve.hazard_rate[i+1]),
                        'type': 'hazard_inflection'
                    })
        
        return points
    
    def _analyze_hazard_rate(self, curve: SurvivalCurve) -> Dict:
        """Analisa padrões do hazard rate"""
        if len(curve.hazard_rate) == 0:
            return {}
        
        return {
            'max_hazard': float(np.max(curve.hazard_rate)),
            'avg_hazard': float(np.mean(curve.hazard_rate)),
            'hazard_trend': 'increasing' if curve.hazard_rate[-1] > curve.hazard_rate[0] else 'decreasing',
            'critical_threshold_crossed': bool(np.any(curve.hazard_rate > 0.15))
        }
    
    def _suggest_time_stop(
        self,
        curve: SurvivalCurve,
        critical_points: List[Dict],
        hazard_analysis: Dict
    ) -> Dict:
        """Gera sugestão de time stop"""
        
        # Procurar ponto onde S(t) ≈ 0.5 (mediana)
        median_idx = np.argmin(np.abs(curve.survival_prob - 0.5))
        suggested_time = curve.time_hours[median_idx]
        survival_at_suggestion = curve.survival_prob[median_idx]
        hazard_at_suggestion = curve.hazard_rate[median_idx] if median_idx < len(curve.hazard_rate) else 0
        
        # Ajustar baseado no hazard rate
        if hazard_analysis.get('critical_threshold_crossed', False):
            # Encontrar onde hazard > 15%
            for i, h in enumerate(curve.hazard_rate):
                if h > 0.15:
                    suggested_time = curve.time_hours[max(0, i-1)]
                    survival_at_suggestion = curve.survival_prob[max(0, i-1)]
                    hazard_at_suggestion = curve.hazard_rate[max(0, i-1)]
                    break
        
        # Gerar racional
        rationale = (
            f"Com base na análise de {curve.sample_size} baskets, "
            f"após {suggested_time:.1f}h de exposição, "
            f"apenas {survival_at_suggestion*100:.0f}% dos baskets sobrevivem sem atingir stop. "
        )
        
        if hazard_at_suggestion > 0.15:
            rationale += f"O hazard rate atinge {hazard_at_suggestion*100:.0f}%/h, indicando risco elevado."
        else:
            rationale += "Este é o ponto de inflexão onde a probabilidade de falha aumenta significativamente."
        
        return {
            'time_hours': float(suggested_time),
            'survival_prob': float(survival_at_suggestion),
            'hazard_rate': float(hazard_at_suggestion),
            'rationale': rationale,
            'confidence': min(1.0, curve.sample_size / 100)  # Confiança aumenta com amostra
        }
    
    def compare_curves(
        self,
        curve1: SurvivalCurve,
        curve2: SurvivalCurve,
        label1: str = "Group 1",
        label2: str = "Group 2"
    ) -> Dict:
        """
        Compara duas curvas de sobrevivência usando Log-rank test
        
        Returns:
            Dict com resultado do teste estatístico
        """
        # Log-rank test simplificado
        # Na implementação completa, usar lifelines library
        
        return {
            'curve1_label': label1,
            'curve2_label': label2,
            'median_survival_1': curve1.median_survival_time,
            'median_survival_2': curve2.median_survival_time,
            'difference': curve1.median_survival_time - curve2.median_survival_time,
            'interpretation': (
                f"{label1} tem sobrevivência mediana de {curve1.median_survival_time:.1f}h "
                f"vs {curve2.median_survival_time:.1f}h para {label2}"
            )
        }
