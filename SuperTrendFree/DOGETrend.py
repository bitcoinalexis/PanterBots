"""
Sistema simplificado de alertas Supertrend
"""

import requests
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime, timedelta
import pytz
from typing import Dict, List


PAIR = "DOGEUSDT" #INGRESAR EL PAR DE TRADING que deseas monitorear

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('supertrend_simple.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SupertrendCalculator:
    """Calculadora del indicador Supertrend"""
    
    def __init__(self, atr_period=10, atr_multiplier=3.0):
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
    
    def calculate_atr(self, data: pd.DataFrame) -> pd.Series:
        """Calcula el Average True Range (ATR)"""
        high = data['high']
        low = data['low']
        close = data['close']
        
        # True Range calculation
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.ewm(span=self.atr_period).mean()
        
        return atr
    
    def calculate_supertrend(self, data: pd.DataFrame) -> Dict:
        """Calcula el indicador Supertrend y retorna señales"""
        if len(data) < self.atr_period + 1:
            return {"trend": 0, "supertrend": 0, "signal": None, "price": 0}
        
        # Calcular ATR
        atr = self.calculate_atr(data)
        
        # Fuente de precios (hl2)
        src = (data['high'] + data['low']) / 2
        
        # Calcular bandas
        up = src - (self.atr_multiplier * atr)
        dn = src + (self.atr_multiplier * atr)
        
        # Inicializar arrays
        up_band = np.zeros(len(data))
        dn_band = np.zeros(len(data))
        trend = np.zeros(len(data))
        
        # Primer valor
        up_band[0] = up.iloc[0]
        dn_band[0] = dn.iloc[0]
        trend[0] = 1
        
        # Calcular bandas y tendencia
        for i in range(1, len(data)):
            # Banda superior
            up_band[i] = up.iloc[i]
            if data['close'].iloc[i-1] > up_band[i-1]:
                up_band[i] = max(up.iloc[i], up_band[i-1])
            
            # Banda inferior
            dn_band[i] = dn.iloc[i]
            if data['close'].iloc[i-1] < dn_band[i-1]:
                dn_band[i] = min(dn.iloc[i], dn_band[i-1])
            
            # Determinar tendencia
            if trend[i-1] == -1 and data['close'].iloc[i] > dn_band[i-1]:
                trend[i] = 1
            elif trend[i-1] == 1 and data['close'].iloc[i] < up_band[i-1]:
                trend[i] = -1
            else:
                trend[i] = trend[i-1]
        
        # Calcular Supertrend
        supertrend = np.where(trend == 1, dn_band, up_band)
        
        # Detectar señales
        current_trend = trend[-1]
        previous_trend = trend[-2] if len(trend) > 1 else current_trend
        
        signal = None
        if current_trend == 1 and previous_trend == -1:
            signal = "LONG"
        elif current_trend == -1 and previous_trend == 1:
            signal = "SHORT"
        
        return {
            "trend": current_trend,
            "supertrend": supertrend[-1],
            "signal": signal,
            "price": data['close'].iloc[-1]
        }

class BybitDataFetcher:
    """Manejador de datos de Bybit"""
    
    def __init__(self, symbol=""):
        self.symbol = symbol
        self.base_url = "https://api.bybit.com"
    
    def get_klines(self, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """Obtiene datos de klines"""
        url = f"{self.base_url}/v5/market/kline"
        
        params = {
            'category': 'linear',
            'symbol': self.symbol,
            'interval': timeframe,
            'limit': limit
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['retCode'] == 0:
                klines = data['result']['list']
                if not klines:
                    return pd.DataFrame()
                
                # Los datos vienen en orden inverso
                klines.reverse()
                
                df = pd.DataFrame(klines, columns=[
                    'start_time', 'open', 'high', 'low', 'close', 'volume', 'turnover'
                ])
                
                # Convertir tipos de datos
                df['start_time'] = pd.to_datetime(df['start_time'].astype(int), unit='ms')
                df['open'] = df['open'].astype(float)
                df['high'] = df['high'].astype(float)
                df['low'] = df['low'].astype(float)
                df['close'] = df['close'].astype(float)
                df['volume'] = df['volume'].astype(float)
                
                df.set_index('start_time', inplace=True)
                return df
            else:
                logger.error(f"Error en API: {data['retMsg']}")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error al obtener datos: {e}")
            return pd.DataFrame()

class TelegramNotifier:
    """Notificador de Telegram"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.mexico_tz = pytz.timezone('America/Mexico_City')
    
    def get_mexico_time(self) -> str:
        """Obtiene la hora actual en la zona horaria configurada"""
        now = datetime.now(self.mexico_tz)
        return now.strftime("%Y-%m-%d %H:%M:%S")
    
    def send_alert(self, signal_data: dict) -> bool:
        """Envía una alerta a Telegram"""
        try:
            timeframe_map = {
                "30": "30 minutos",
                "60": "1 hora", 
                "240": "4 horas"
            }
            
            timeframe_name = timeframe_map.get(signal_data['timeframe'], signal_data['timeframe'])
            mexico_time = self.get_mexico_time()
            
            # Crear mensaje
            if signal_data['signal'] == "LONG":
                emoji = "🟢"
                action = "COMPRA"
            else:
                emoji = "🔴"
                action = "VENTA"
            
            message = f"""{emoji} **ALERTA SUPERTREND - **

**Hora CDMX:** {mexico_time}
**Timeframe:** {timeframe_name}
**Precio:** ${signal_data['price']:.4f}
**Supertrend:** ${signal_data['supertrend']:.4f}
**Senal:** {signal_data['signal']} ({action})

#Supertrend #DOG{PAIR} #{signal_data['signal']}

            """.strip()
            
            # Enviar mensaje
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Alerta enviada: {signal_data['signal']} en {timeframe_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando alerta a Telegram: {e}")
            return False

class SupertrendAlertSystem:
    """Sistema principal de alertas Supertrend"""
    
    def __init__(self):
        # Cargar configuración
        from config import AlertConfig
        config = AlertConfig()
        
        self.symbol = config.SYMBOL
        self.timeframes = config.TIMEFRAMES
        self.atr_period = config.ATR_PERIOD
        self.atr_multiplier = config.ATR_MULTIPLIER
        
        self.data_fetcher = BybitDataFetcher(self.symbol)
        self.calculator = SupertrendCalculator(self.atr_period, self.atr_multiplier)
        self.telegram = TelegramNotifier(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
        
        # Almacenar últimas señales para evitar duplicados
        self.last_signals = {tf: None for tf in self.timeframes}
        
        logger.info(f"Sistema inicializado para {self.symbol}")
        logger.info(f"Timeframes: {', '.join(self.timeframes)}")
    
    def check_signals(self):
        """Verifica señales en todos los timeframes"""
        for timeframe in self.timeframes:
            try:
                # Obtener datos
                df = self.data_fetcher.get_klines(timeframe, limit=50)
                
                if df.empty:
                    logger.warning(f"No hay datos para timeframe {timeframe}")
                    continue
                
                # Calcular Supertrend
                result = self.calculator.calculate_supertrend(df)
                
                # Verificar si hay nueva señal
                if result['signal'] and result['signal'] != self.last_signals[timeframe]:
                    self.last_signals[timeframe] = result['signal']
                    
                    # Crear datos de señal
                    signal_data = {
                        'timeframe': timeframe,
                        'signal': result['signal'],
                        'price': result['price'],
                        'supertrend': result['supertrend']
                    }
                    
                    # Enviar alerta
                    success = self.telegram.send_alert(signal_data)
                    if success:
                        logger.info(f"Señal {result['signal']} enviada para {timeframe}")
                
            except Exception as e:
                logger.error(f"Error verificando señales para {timeframe}: {e}")
    
    def run(self):
        """Ejecuta el sistema de alertas"""
        logger.info("Iniciando sistema de alertas...")
        
        while True:
            try:
                self.check_signals()
                time.sleep(8)  # Verificar cada minuto
                
            except KeyboardInterrupt:
                logger.info("Sistema detenido por el usuario")
                break
            except Exception as e:
                logger.error(f"Error en el sistema: {e}")
                time.sleep(60)

def main():
    """Función principal"""
    try:
        system = SupertrendAlertSystem()
        system.run()
    except Exception as e:
        logger.error(f"Error iniciando el sistema: {e}")

if __name__ == "__main__":
    main()
