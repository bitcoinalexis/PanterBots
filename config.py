# Configuración del sistema de alertas Supertrend
# Generado automáticamente

class AlertConfig:
    """Configuración para las alertas de Supertrend"""
    
    # Configuración de Telegram - INGRESAR TOKEN Y CHAT ID
    TELEGRAM_BOT_TOKEN = ""
    TELEGRAM_CHAT_ID = ""
    
    # Configuración de Bybit - INGRESAR API KEY Y API SECRET
    BYBIT_API_KEY = ""
    BYBIT_API_SECRET = ""
    
    # Configuración del indicador
    SYMBOL = "DOGEUSDT"
    TIMEFRAMES = ["30", "60", "240"]  # 30m, 1h, 4h
    ATR_PERIOD = 10
    ATR_MULTIPLIER = 3.0
    
    # Configuración adicional
    TIMEZONE = "America/New_York" #COLOCAR LA ZONA HORARIA DE LA CIUDAD
    RECONNECT_INTERVAL = 5
    MAX_HISTORICAL_RECORDS = 200
