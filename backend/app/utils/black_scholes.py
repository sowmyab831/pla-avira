"""
Black-Scholes options pricing and Greeks calculation
"""

import numpy as np
from scipy.stats import norm
from typing import Dict, Literal


class BlackScholesCalculator:
    """
    Calculate options prices and Greeks using Black-Scholes model
    """
    
    def calculate_greeks(
        self,
        S: float,  # Current stock price
        K: float,  # Strike price
        T: float,  # Time to expiration (years)
        r: float,  # Risk-free rate
        sigma: float,  # Implied volatility
        option_type: Literal['call', 'put'] = 'call'
    ) -> Dict[str, float]:
        """
        Calculate all Greeks for an option
        
        Returns:
            Dictionary with price, delta, gamma, theta, vega, rho
        """
        # Handle edge cases
        if T <= 0:
            return self._handle_expiration(S, K, option_type)
        
        if sigma <= 0:
            sigma = 0.01  # Minimum volatility
        
        # Calculate d1 and d2
        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        # Calculate price
        if option_type == 'call':
            price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
            delta = norm.cdf(d1)
            theta = (
                -S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                - r * K * np.exp(-r * T) * norm.cdf(d2)
            ) / 365  # Convert to daily theta
            rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100
        else:  # put
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            delta = -norm.cdf(-d1)
            theta = (
                -S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                + r * K * np.exp(-r * T) * norm.cdf(-d2)
            ) / 365  # Convert to daily theta
            rho = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100
        
        # Calculate gamma (same for calls and puts)
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        
        # Calculate vega (same for calls and puts)
        vega = S * norm.pdf(d1) * np.sqrt(T) / 100  # Divide by 100 for 1% change
        
        return {
            'price': round(price, 2),
            'delta': round(delta, 4),
            'gamma': round(gamma, 4),
            'theta': round(theta, 4),
            'vega': round(vega, 4),
            'rho': round(rho, 4)
        }
    
    def _handle_expiration(
        self,
        S: float,
        K: float,
        option_type: Literal['call', 'put']
    ) -> Dict[str, float]:
        """
        Handle options at expiration (T = 0)
        """
        if option_type == 'call':
            price = max(0, S - K)
            delta = 1.0 if S > K else 0.0
        else:
            price = max(0, K - S)
            delta = -1.0 if S < K else 0.0
        
        return {
            'price': round(price, 2),
            'delta': delta,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0
        }
    
    def calculate_iv_rank(
        self,
        current_iv: float,
        iv_history: list[float]
    ) -> float:
        """
        Calculate IV Rank (52-week basis)
        
        IV Rank = (Current IV - Min IV) / (Max IV - Min IV) * 100
        """
        if not iv_history:
            return 50.0  # Default to middle
        
        min_iv = min(iv_history)
        max_iv = max(iv_history)
        
        if max_iv == min_iv:
            return 50.0
        
        iv_rank = ((current_iv - min_iv) / (max_iv - min_iv)) * 100
        return round(iv_rank, 2)
    
    def calculate_probability_of_profit(
        self,
        S: float,
        K: float,
        T: float,
        sigma: float,
        option_type: Literal['call', 'put']
    ) -> float:
        """
        Calculate probability of profit at expiration
        """
        if T <= 0:
            if option_type == 'call':
                return 1.0 if S > K else 0.0
            else:
                return 1.0 if S < K else 0.0
        
        # Calculate probability using normal distribution
        d2 = (np.log(S / K) + (0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        
        if option_type == 'call':
            prob = norm.cdf(d2)
        else:
            prob = norm.cdf(-d2)
        
        return round(prob, 4)
    
    def calculate_breakeven(
        self,
        K: float,
        premium: float,
        option_type: Literal['call', 'put']
    ) -> float:
        """
        Calculate breakeven price at expiration
        """
        if option_type == 'call':
            return round(K + premium, 2)
        else:
            return round(K - premium, 2)
    
    def calculate_max_profit(
        self,
        premium: float,
        contracts: int = 1,
        option_type: Literal['call', 'put'] = 'call',
        strategy: str = 'long'
    ) -> float:
        """
        Calculate maximum profit for a strategy
        """
        multiplier = 100  # Options multiplier
        
        if strategy == 'long':
            if option_type == 'call':
                return float('inf')  # Unlimited for long calls
            else:
                # Max profit for long put is strike - premium
                return premium * contracts * multiplier
        
        elif strategy == 'short':
            # Max profit for short options is premium collected
            return premium * contracts * multiplier
        
        return 0.0
    
    def calculate_max_loss(
        self,
        premium: float,
        K: float,
        contracts: int = 1,
        option_type: Literal['call', 'put'] = 'call',
        strategy: str = 'long'
    ) -> float:
        """
        Calculate maximum loss for a strategy
        """
        multiplier = 100  # Options multiplier
        
        if strategy == 'long':
            # Max loss for long options is premium paid
            return premium * contracts * multiplier
        
        elif strategy == 'short':
            if option_type == 'call':
                return float('inf')  # Unlimited for short calls
            else:
                # Max loss for short put is strike - premium
                return (K - premium) * contracts * multiplier
        
        return 0.0
