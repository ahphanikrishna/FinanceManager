import pdfplumber
import pandas as pd
import msoffcrypto
import io
import datetime
import re

from sqlalchemy import text

def clean_amt(val):
    return float(val.replace(',', '')) if val and val.strip() else 0.0


def parse_hdfc_cc_pdf(file_path, password=None):
    transactions = []
    try:
        # Use the password argument here
        with pdfplumber.open(file_path, password=password) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if table[0] == ['DATE & TIME TRANSACTION DESCRIPTION AMOUNT PI']:
                        for row in table[1:]:
                            # Regex breakdown:
                            # (\d{2}/\d{2}/\d{4})        -> Captures Date (DD/MM/YYYY)
                            # \|?\s* -> Matches optional pipe and spaces
                            # ([\d{2}:\d{2}]*)?          -> Matches optional Time
                            # \s*(.*?)\s* -> Captures Description (non-greedy)
                            # (\d+\.\d{2})               -> Captures Amount (digits + . + 2 digits)
                            pattern = r"(\d{2}/\d{2}/\d{4})\|?\s*([\d:]*)\s*(.*?)\s*(\d+\.\d{2})"
                            
                            match = re.search(pattern, row[0].replace(",", ""))
                            
                            if match:
                                transactions.append({
                                    "date": datetime.datetime.strptime(match.group(1), "%d/%m/%Y"),
                                    "description": match.group(3).strip(),
                                    "type": "Transfer" if "AUTOPAY THANK YOU" in match.group(3).strip() else "Expenditure",  # Assuming all are expenditures for credit card
                                    "amount": float(match.group(4)) if "AUTOPAY THANK YOU" in match.group(3).strip() else -1 * float(match.group(4))
                                })
        return transactions
    except Exception as e:
        print(f"Error unlocking PDF: {e}")
        return None
    

def clean_amt(val):
    return float(val.replace(',', '')) if val and val.strip() else 0.0

if __name__ == "__main__":
    file_path = "C:/Users/Phani/Desktop/Jan2026_Billedstatements_3166_20-02-26_09-55.pdf"
    password = ""  # Replace with actual password
    data = parse_hdfc_cc_pdf(file_path, password=password)