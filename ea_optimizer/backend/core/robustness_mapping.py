"""
EA Configuration Optimizer v1.2
Robustness Mapping Module
FR-16: Parameter Sensitivity & 3D Surface Analysis

O sistema não deve otimizar para "picos isolados" de performance (overfitting),
mas para planícies de estabilidade (robustness zones).

Requisito de Vizinhança:
Uma configuração (Grid, Multiplier) só é considerada "Estável" se:
Score(Grid ± Δ, Multiplier ± δ) > 0.8 × Score(ótimo) para pelo menos 80% dos vizinhos
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter

@dataclass
class RobustnessMetrics:
    """Métricas de robustez para uma configuração"""
    grid_pips: int
    multiplier: float
    atr_filter: float
    
    # Scores
    optimization_score: float  # Score central
    neighbor_stability_pct: float  # % de vizinhos com >80% do score
    is_robust: bool  # TRUE se stability_pct >= 80%
    
    # Estatísticas de vizinhança
    score_std_dev: float
    score_gradient: float
    neighbor_scores: Dict[str, float]
    
    # Metadados
    neighborhood_radius: int = 2  # Raio de ±2 steps
    stability_threshold: float = 0.8  # 80% do score ótimo

class RobustnessLandscape:
    """
    Mapeamento completo do landscape de robustez paramétrica
    """
    
    def __init__(
        self,
        grid_range: Tuple[int, int] = (200, 500),
        multiplier_range: Tuple[float, float] = (1.2, 1.6),
        atr_range: Tuple[float, float] = (1.0, 2.0),
        grid_step: int = 10,
        multiplier_step: float = 0.05,
        atr_step: float = 0.1
    ):
        self.grid_range = grid_range
        self.multiplier_range = multiplier_range
        self.atr_range = atr_range
        self.grid_step = grid_step
        self.multiplier_step = multiplier_step
        self.atr_step = atr_step
        
        # Gerar grid de parâmetros
        self.grid_values = list(range(grid_range[0], grid_range[1] + 1, grid_step))
        self.multiplier_values = np.arange(multiplier_range[0], multiplier_range[1] + 0.001, multiplier_step)
        self.atr_values = np.arange(atr_range[0], atr_range[1] + 0.001, atr_step)
    
    def calculate_robustness(
        self,
        optimization_results: pd.DataFrame,
        center_grid: int,
        center_multiplier: float,
        center_atr: float,
        neighborhood_radius: int = 2
    ) -> RobustnessMetrics:
        """
        Calcula robustez de uma configuração analisando vizinhança
        
        Args:
            optimization_results: DataFrame com resultados de otimização
            center_grid: Valor central de grid spacing
            center_multiplier: Valor central de lot multiplier
            center_atr: Valor central de ATR filter
            neighborhood_radius: Raio de vizinhança (±steps)
        
        Returns:
            RobustnessMetrics
        """
        # Encontrar score central
        center_score = self._get_score(
            optimization_results,
            center_grid,
            center_multiplier,
            center_atr
        )
        
        if center_score is None or center_score == 0:
            return RobustnessMetrics(
                grid_pips=center_grid,
                multiplier=center_multiplier,
                atr_filter=center_atr,
                optimization_score=0.0,
                neighbor_stability_pct=0.0,
                is_robust=False,
                score_std_dev=0.0,
                score_gradient=0.0,
                neighbor_scores={}
            )
        
        # Coletar scores dos vizinhos
        neighbor_scores = {}
        stable_neighbors = 0
        total_neighbors = 0
        
        for dg in range(-neighborhood_radius, neighborhood_radius + 1):
            for dm in range(-neighborhood_radius, neighborhood_radius + 1):
                for da in range(-neighborhood_radius, neighborhood_radius + 1):
                    # Pular o centro
                    if dg == 0 and dm == 0 and da == 0:
                        continue
                    
                    neighbor_grid = center_grid + dg * self.grid_step
                    neighbor_mult = center_multiplier + dm * self.multiplier_step
                    neighbor_atr = center_atr + da * self.atr_step
                    
                    # Verificar se está dentro dos limites
                    if not self._is_valid_params(neighbor_grid, neighbor_mult, neighbor_atr):
                        continue
                    
                    score = self._get_score(
                        optimization_results,
                        neighbor_grid,
                        neighbor_mult,
                        neighbor_atr
                    )
                    
                    key = f"grid_{neighbor_grid}_mult_{neighbor_mult:.2f}_atr_{neighbor_atr:.1f}"
                    neighbor_scores[key] = score if score is not None else 0.0
                    
                    total_neighbors += 1
                    
                    # Verificar estabilidade (score > 80% do central)
                    if score is not None and score > 0.8 * center_score:
                        stable_neighbors += 1
        
        # Calcular métricas
        stability_pct = (stable_neighbors / total_neighbors * 100) if total_neighbors > 0 else 0.0
        scores_array = np.array(list(neighbor_scores.values()))
        
        score_std = np.std(scores_array) if len(scores_array) > 0 else 0.0
        score_gradient = self._calculate_gradient(neighbor_scores, center_score)
        
        return RobustnessMetrics(
            grid_pips=center_grid,
            multiplier=center_multiplier,
            atr_filter=center_atr,
            optimization_score=center_score,
            neighbor_stability_pct=stability_pct,
            is_robust=stability_pct >= 80.0,
            score_std_dev=score_std,
            score_gradient=score_gradient,
            neighbor_scores=neighbor_scores,
            neighborhood_radius=neighborhood_radius
        )
    
    def build_landscape(
        self,
        optimization_results: pd.DataFrame,
        fixed_atr: Optional[float] = None
    ) -> pd.DataFrame:
        """
        Constrói landscape completo de robustez
        
        Args:
            optimization_results: DataFrame com todos os resultados
            fixed_atr: Se especificado, fixa ATR e faz 2D (grid x multiplier)
        
        Returns:
            DataFrame com landscape de robustez
        """
        landscape_data = []
        
        atr_values = [fixed_atr] if fixed_atr else self.atr_values
        
        for atr in atr_values:
            for grid in self.grid_values:
                for mult in self.multiplier_values:
                    metrics = self.calculate_robustness(
                        optimization_results,
                        grid,
                        mult,
                        atr
                    )
                    
                    landscape_data.append({
                        'grid_pips': grid,
                        'multiplier': mult,
                        'atr_filter': atr,
                        'optimization_score': metrics.optimization_score,
                        'neighbor_stability_pct': metrics.neighbor_stability_pct,
                        'is_robust': metrics.is_robust,
                        'score_std_dev': metrics.score_std_dev,
                        'score_gradient': metrics.score_gradient
                    })
        
        return pd.DataFrame(landscape_data)
    
    def find_robust_zones(
        self,
        landscape: pd.DataFrame,
        min_stability: float = 80.0,
        min_score: float = 50.0
    ) -> List[Dict]:
        """
        Encontra zonas de robustez (planícies de estabilidade)
        
        Returns:
            Lista de zonas robustas encontradas
        """
        robust_zones = []
        
        # Verificar se colunas necessárias existem
        if 'is_robust' not in landscape.columns:
            # Se não temos dados de robustez completos, usar apenas score
            robust_configs = landscape[landscape['optimization_score'] >= min_score]
        else:
            # Filtrar configurações robustas
            robust_configs = landscape[
                (landscape['is_robust'] == True) &
                (landscape['neighbor_stability_pct'] >= min_stability) &
                (landscape['optimization_score'] >= min_score)
            ]
        
        if len(robust_configs) == 0:
            return robust_zones
        
        # Agrupar por proximidade (clustering simples)
        clustered = self._cluster_robust_configs(robust_configs)
        
        for cluster_id, cluster_df in clustered.items():
            if len(cluster_df) == 0:
                continue
            
            # Encontrar melhor configuração no cluster
            best_idx = cluster_df['optimization_score'].idxmax()
            best = cluster_df.loc[best_idx]
            
            zone = {
                'cluster_id': cluster_id,
                'center_grid': int(best['grid_pips']),
                'center_multiplier': float(best['multiplier']),
                'atr_filter': float(best['atr_filter']),
                'optimization_score': float(best['optimization_score']),
                'avg_stability': float(cluster_df['neighbor_stability_pct'].mean()),
                'cluster_size': len(cluster_df),
                'grid_range': (
                    int(cluster_df['grid_pips'].min()),
                    int(cluster_df['grid_pips'].max())
                ),
                'multiplier_range': (
                    float(cluster_df['multiplier'].min()),
                    float(cluster_df['multiplier'].max())
                )
            }
            
            robust_zones.append(zone)
        
        # Ordenar por score
        robust_zones.sort(key=lambda x: x['optimization_score'], reverse=True)
        
        return robust_zones
    
    def find_overfitting_peaks(
        self,
        landscape: pd.DataFrame,
        stability_threshold: float = 50.0
    ) -> List[Dict]:
        """
        Encontra picos de overfitting (alta performance, baixa estabilidade)
        
        Returns:
            Lista de picos de overfitting
        """
        peaks = []
        
        # Configurações com alto score mas baixa estabilidade
        overfitting = landscape[
            (landscape['optimization_score'] > 80) &
            (landscape['neighbor_stability_pct'] < stability_threshold)
        ]
        
        for _, row in overfitting.iterrows():
            peak = {
                'grid_pips': int(row['grid_pips']),
                'multiplier': float(row['multiplier']),
                'atr_filter': float(row['atr_filter']),
                'optimization_score': float(row['optimization_score']),
                'stability_pct': float(row['neighbor_stability_pct']),
                'std_dev': float(row['score_std_dev']),
                'warning': (
                    f"Configuração Grid={int(row['grid_pips'])}/Mult={row['multiplier']:.2f} "
                    f"apresenta Score={row['optimization_score']:.0f}, mas vizinhos caem para "
                    f"Score={row['optimization_score'] * row['neighbor_stability_pct'] / 100:.0f} "
                    f"({row['neighbor_stability_pct']:.0f}% de estabilidade). "
                    f"EVITAR - Pico de overfitting detectado."
                )
            }
            peaks.append(peak)
        
        return sorted(peaks, key=lambda x: x['optimization_score'], reverse=True)
    
    def generate_recommendation(
        self,
        landscape: pd.DataFrame,
        current_config: Optional[Dict] = None
    ) -> Dict:
        """
        Gera recomendação de configuração robusta
        
        Returns:
            Dict com recomendação detalhada
        """
        # Encontrar zonas robustas
        robust_zones = self.find_robust_zones(landscape)
        
        # Encontrar picos de overfitting
        overfitting_peaks = self.find_overfitting_peaks(landscape)
        
        if not robust_zones:
            return {
                'recommendation': 'Nenhuma zona robusta encontrada. Considere expandir o espaço de busca.',
                'best_available': landscape.loc[landscape['optimization_score'].idxmax()].to_dict(),
                'robust_zones': [],
                'overfitting_warnings': overfitting_peaks[:3]
            }
        
        # Melhor zona robusta
        best_zone = robust_zones[0]
        
        recommendation = {
            'recommended_config': {
                'grid_pips': best_zone['center_grid'],
                'multiplier': best_zone['center_multiplier'],
                'atr_filter': best_zone['atr_filter']
            },
            'expected_performance': {
                'optimization_score': best_zone['optimization_score'],
                'stability': best_zone['avg_stability']
            },
            'rationale': (
                f"Configuração robusta: Grid={best_zone['center_grid']}/"
                f"Mult={best_zone['center_multiplier']:.2f} com Score={best_zone['optimization_score']:.0f} "
                f"e estabilidade vizinha de {best_zone['avg_stability']:.0f}% (zona azul). "
                f"Tolerante a variações de mercado."
            ),
            'robust_zones': robust_zones[:5],
            'overfitting_warnings': overfitting_peaks[:3]
        }
        
        # Se há configuração atual, comparar
        if current_config:
            current_robustness = self.calculate_robustness(
                landscape,
                current_config.get('grid_pips', 300),
                current_config.get('multiplier', 1.3),
                current_config.get('atr_filter', 1.5)
            )
            
            if not current_robustness.is_robust:
                recommendation['migration_advice'] = (
                    f"Sua configuração atual tem apenas {current_robustness.neighbor_stability_pct:.0f}% "
                    f"de estabilidade. Migre para a configuração recomendada para reduzir risco de overfitting."
                )
        
        return recommendation
    
    def _get_score(
        self,
        results: pd.DataFrame,
        grid: int,
        multiplier: float,
        atr: float
    ) -> Optional[float]:
        """Busca score para configuração específica"""
        match = results[
            (abs(results['grid_pips'] - grid) < self.grid_step / 2) &
            (abs(results['multiplier'] - multiplier) < self.multiplier_step / 2) &
            (abs(results['atr_filter'] - atr) < self.atr_step / 2)
        ]
        
        if len(match) > 0:
            return float(match.iloc[0]['optimization_score'])
        return None
    
    def _is_valid_params(self, grid: int, multiplier: float, atr: float) -> bool:
        """Verifica se parâmetros estão dentro dos limites válidos"""
        return (
            self.grid_range[0] <= grid <= self.grid_range[1] and
            self.multiplier_range[0] <= multiplier <= self.multiplier_range[1] and
            self.atr_range[0] <= atr <= self.atr_range[1]
        )
    
    def _calculate_gradient(self, neighbor_scores: Dict[str, float], center_score: float) -> float:
        """Calcula gradiente médio ao redor do ponto central"""
        if not neighbor_scores:
            return 0.0
        
        differences = [abs(score - center_score) for score in neighbor_scores.values()]
        return np.mean(differences) if differences else 0.0
    
    def _cluster_robust_configs(
        self,
        robust_configs: pd.DataFrame,
        max_distance: int = 20
    ) -> Dict[int, pd.DataFrame]:
        """Agrupa configurações robustas por proximidade"""
        if len(robust_configs) == 0:
            return {}
        
        clusters = {}
        cluster_id = 0
        assigned = set()
        
        for idx, row in robust_configs.iterrows():
            if idx in assigned:
                continue
            
            # Novo cluster
            cluster_members = [idx]
            assigned.add(idx)
            
            # Encontrar vizinhos
            for other_idx, other_row in robust_configs.iterrows():
                if other_idx in assigned:
                    continue
                
                distance = np.sqrt(
                    (row['grid_pips'] - other_row['grid_pips']) ** 2 +
                    ((row['multiplier'] - other_row['multiplier']) * 100) ** 2
                )
                
                if distance <= max_distance:
                    cluster_members.append(other_idx)
                    assigned.add(other_idx)
            
            clusters[cluster_id] = robust_configs.loc[cluster_members]
            cluster_id += 1
        
        return clusters
    
    def interpolate_surface(
        self,
        landscape: pd.DataFrame,
        resolution: int = 100
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Interpola superfície 3D para visualização
        
        Returns:
            Tuple de (X, Y, Z) para plotagem 3D
        """
        # Criar grid regular
        xi = np.linspace(
            landscape['grid_pips'].min(),
            landscape['grid_pips'].max(),
            resolution
        )
        yi = np.linspace(
            landscape['multiplier'].min(),
            landscape['multiplier'].max(),
            resolution
        )
        xi, yi = np.meshgrid(xi, yi)
        
        # Interpolar scores
        points = landscape[['grid_pips', 'multiplier']].values
        values = landscape['optimization_score'].values
        
        zi = griddata(points, values, (xi, yi), method='cubic')
        
        # Suavizar
        zi = gaussian_filter(zi, sigma=1.0)
        
        return xi, yi, zi
