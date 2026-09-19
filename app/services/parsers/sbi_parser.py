import pdfplumber
import pandas as pd
import msoffcrypto
import io
import datetime
import numpy as np

def parse_sbi_pdf(file_path, password=None):
    transactions = []
    try:
        # Use the password argument here
        with pdfplumber.open(file_path, password=password) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if not table: continue
                
                for row in table[1:]:
                    if not row[0]: continue
                    
                    def clean_amt(val):
                        return float(val.replace(',', '')) if val and val.strip() else 0.0

                    transactions.append({
                        "date": row[0],
                        "description": row[1],
                        "amount": clean_amt(row[4]) - clean_amt(row[3]),
                        "bank_name": "SBI"
                    })
        return transactions
    except Exception as e:
        print(f"Error unlocking PDF: {e}")
        return None
    
def parse_sbi_excel(file_path, password=None):
    # Placeholder for Excel parsing logic
    # Implement Excel parsing with password handling if needed
    transactions = []
    try:

        # Decrypt the Excel file using msoffcrypto
        decrypted_workbook = io.BytesIO()
        with open(file_path, 'rb') as file:
            office_file = msoffcrypto.OfficeFile(file)
            office_file.load_key(password=password)
            office_file.decrypt(decrypted_workbook)

        df = pd.read_excel(decrypted_workbook, skiprows=10) 
        
        # Find the correct header row and the table data
        start_index = [i for i, x in enumerate(df.iloc[:,0]) if x == 'Date'][0]
        df.columns = df.iloc[start_index, :].values
        df = df.iloc[start_index +1:, :].reset_index(drop=True)

        end_index = [i for i, x in enumerate(df.iloc[:,0]) if str(x) == "nan"][0]
        df = df.iloc[:end_index, :]

        # Clean column names (remove extra spaces)
        df.columns = [str(c).strip() for c in df.columns]    

        for row in df.itertuples(index=False):
            if not row[0]: continue

            transactions.append({
                "date": datetime.datetime.strptime(row[0], "%d/%m/%Y"),
                "description": row[1],
                "type": "Income" if pd.isna(row[3]) else "Expenditure",
                "amount": float(row[4]) if pd.isna(row[3]) else -1 * float(row[3]),
                
            })
        
        return transactions
    except Exception as e:
        print(f"Error unlocking Excel: {e}")
        return None

def clean_amt(val):
    return float(val.replace(',', '')) if val and val.strip() else 0.0

if __name__ == "__main__":
    file_path = "C:\\Users\\Phani\\Documents\\Python Scripts\\projects\\Statements\\backend\\uploads\\AccountStatement_29012026_102628.xlsx"
    password = "HANUM03121989"  # Replace with actual password
    data = parse_sbi_excel(file_path, password=password)