def format_currency(amount: float, currency_code: str = 'INR') -> str:
    """
    Format a float amount into a currency string.
    Supports INR with Indian digit grouping (e.g. ₹1,00,000.00)
    and USD with standard grouping (e.g. $100,000.00).
    """
    is_negative = amount < 0
    amount = abs(amount)
    
    if currency_code == 'USD':
        formatted = f"${amount:,.2f}"
    else:
        s = f"{amount:.2f}"
        integer_part, decimal_part = s.split('.')
        
        if len(integer_part) > 3:
            last_3 = integer_part[-3:]
            rest = integer_part[:-3]
            rest_formatted = ""
            while len(rest) > 2:
                rest_formatted = "," + rest[-2:] + rest_formatted
                rest = rest[:-2]
            rest_formatted = rest + rest_formatted
            integer_part = rest_formatted + "," + last_3
            
        formatted = f"₹{integer_part}.{decimal_part}"
        
    if is_negative:
        return "-" + formatted
    return formatted
