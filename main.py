from fastapi import FastAPI, HTTPException
import xmlrpc.client
import sqlalchemy
from sqlalchemy import create_engine, Column, String, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import requests

# FastAPI App
app = FastAPI()

# Odoo configuration
ODOO_URL = "http://localhost:8060"
DATABASE_NAME = "odoo"
USERNAME = "admin"
PASSWORD = "yourpasword"
common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
uid = common.authenticate(DATABASE_NAME, USERNAME, PASSWORD, {})
models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')

# PostgreSQL Configuration
DATABASE_URL = "postgresql://postgres:1234@localhost:5432/fastodoo"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# PostgreSQL Model
class LetterHTML(Base):
    __tablename__ = "letters"
    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(String, index=True)
    html_content = Column(Text)


Base.metadata.create_all(bind=engine)


@app.post("/store_letter/{public_id}")
def store_letter(public_id: str):
    # Fetch from Odoo
    domain = [[['public_id', '=', public_id]]]
    letter_ids = models.execute_kw(DATABASE_NAME, uid, PASSWORD, 'supreme.court.letter', 'search', domain)

    if not letter_ids:
        raise HTTPException(status_code=404, detail="Letter not found in Odoo")

    letter_data = models.execute_kw(DATABASE_NAME, uid, PASSWORD, 'supreme.court.letter', 'read', [letter_ids],
                                    {'fields': ['custom_url']})
    custom_url = letter_data[0].get('custom_url')

    if not custom_url:
        raise HTTPException(status_code=404, detail="Custom URL not found in Odoo")

    # Fetch the actual HTML content from the custom URL
    response = requests.get(custom_url, auth=(USERNAME, PASSWORD))
    response.raise_for_status()  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
    html_content = response.text

    # Store in PostgreSQL
    session = SessionLocal()
    try:
        new_letter = LetterHTML(public_id=public_id, html_content=html_content)
        session.add(new_letter)
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

    return {"message": "Stored successfully"}


@app.get("/render_letter/{public_id}")
def render_letter(public_id: str):
    session = SessionLocal()
    try:
        letter = session.query(LetterHTML).filter(LetterHTML.public_id == public_id).first()
        if not letter:
            raise HTTPException(status_code=404, detail="Letter not found in database")
        return {"html_content": letter.html_content}
    finally:
        session.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
