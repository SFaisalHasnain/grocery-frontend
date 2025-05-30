from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# JWT Configuration
SECRET_KEY = os.environ.get("SECRET_KEY", "uk_grocery_comparison_app_secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week

# Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

# Scheduler for price updates
scheduler = AsyncIOScheduler()

# UK Top Grocery Retailers
UK_GROCERY_RETAILERS = [
    {"name": "Tesco", "url": "https://www.tesco.com", "scraper_function": "scrape_tesco"},
    {"name": "Sainsbury's", "url": "https://www.sainsburys.co.uk", "scraper_function": "scrape_sainsburys"},
    {"name": "Asda", "url": "https://www.asda.com", "scraper_function": "scrape_asda"},
    {"name": "Morrisons", "url": "https://groceries.morrisons.com", "scraper_function": "scrape_morrisons"},
    {"name": "Aldi", "url": "https://www.aldi.co.uk", "scraper_function": "scrape_aldi"},
    {"name": "Lidl", "url": "https://www.lidl.co.uk", "scraper_function": "scrape_lidl"},
    {"name": "Waitrose", "url": "https://www.waitrose.com", "scraper_function": "scrape_waitrose"},
    {"name": "Co-op", "url": "https://www.coop.co.uk", "scraper_function": "scrape_coop"},
    {"name": "M&S", "url": "https://www.marksandspencer.com", "scraper_function": "scrape_marks_spencer"},
    {"name": "Iceland", "url": "https://www.iceland.co.uk", "scraper_function": "scrape_iceland"},
    {"name": "Amazon", "url": "https://www.amazon.co.uk", "scraper_function": "scrape_amazon"}
]

# Define Models
class UserBase(BaseModel):
    email: EmailStr
    
class UserCreate(UserBase):
    password: str
    name: str

class User(UserBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class ProductBase(BaseModel):
    name: str
    category: str
    weight: Optional[str] = None
    quantity: Optional[int] = None
    unit: Optional[str] = None
    
class ProductCreate(ProductBase):
    image_url: Optional[str] = None
    
class Product(ProductBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    image_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class PriceBase(BaseModel):
    product_id: str
    store: str
    price: float
    
class PriceCreate(PriceBase):
    pass

class Price(PriceBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
class ShoppingListItemBase(BaseModel):
    product_id: str
    quantity: int = 1
    
class ShoppingListItemCreate(ShoppingListItemBase):
    pass

class ShoppingListItem(ShoppingListItemBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
class ShoppingListBase(BaseModel):
    name: str
    user_id: str
    
class ShoppingListCreate(ShoppingListBase):
    items: List[ShoppingListItemCreate] = []

class ShoppingList(ShoppingListBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    items: List[ShoppingListItem] = []

class SearchResponse(BaseModel):
    products: List[Product]
    prices: Dict[str, List[Price]]

class StoreInfo(BaseModel):
    name: str
    url: str

# Security Functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

async def get_user(email: str):
    user = await db.users.find_one({"email": email})
    if user:
        return UserInDB(**user)

async def authenticate_user(email: str, password: str):
    user = await get_user(email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except jwt.PyJWTError:
        raise credentials_exception
    user = await get_user(token_data.email)
    if user is None:
        raise credentials_exception
    return user

# Web Scraping Functions
async def scrape_tesco(product_name: str) -> List[Dict[str, Any]]:
    # This is a mock implementation for the MVP
    # In a real-world implementation, we would perform actual web scraping
    await asyncio.sleep(0.1)  # Simulate network delay
    
    # Generate mock results for Tesco
    results = []
    variations = ["", "Organic", "Finest", "Value"]
    prices = [1.50, 2.25, 3.50, 0.99]
    weights = ["500g", "1kg", "250g", "750g"]
    quantities = [1, 4, 6, 12]
    units = ["pack", "box", "bag", "carton"]
    
    for i in range(3):
        variation = variations[i % len(variations)]
        product_type = ""
        display_name = ""
        image_url = ""
        weight = None
        quantity = None
        unit = None
        
        # Format product name based on type
        if "egg" in product_name.lower():
            # Eggs are sold by quantity, not weight
            quantity = [6, 12, 15, 10][i % 4]
            unit = "pack"
            display_name = f"{variation} {product_name} {quantity} {unit}".strip()
            product_type = "Dairy & Eggs"
            weight = None
            
        elif "milk" in product_name.lower():
            # Milk typically sold in volume
            volume = ["1 pint", "2 pints", "4 pints", "6 pints"][i % 4]
            display_name = f"{variation} {product_name} {volume}".strip()
            product_type = "Dairy"
            weight = None
            unit = "bottle"
            
        elif "bread" in product_name.lower():
            # Bread typically sold by loaf
            weight = ["400g", "800g", "600g"][i % 3]
            display_name = f"{variation} {product_name} {weight} loaf".strip()
            product_type = "Bakery"
            unit = "loaf"
            
        elif "apple" in product_name.lower() or "banana" in product_name.lower() or "fruit" in product_name.lower():
            if "apple" in product_name.lower() or "orange" in product_name.lower():
                # Apples/oranges often sold individually or in packs
                quantity = [4, 6, 8][i % 3]
                display_name = f"{variation} {product_name} {quantity} pack".strip()
                unit = "pack"
            else:
                # Other fruit sold by weight
                weight = weights[i % len(weights)]
                display_name = f"{variation} {product_name} {weight}".strip()
                unit = "bag"
            product_type = "Produce"
            
        elif "chicken" in product_name.lower() or "beef" in product_name.lower() or "pork" in product_name.lower():
            # Meat sold by weight
            weight = weights[i % len(weights)]
            display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Meat"
            unit = "package"
            
        elif "pasta" in product_name.lower() or "rice" in product_name.lower():
            # Pasta/rice sold by weight
            weight = ["500g", "1kg", "750g"][i % 3]
            display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Pantry"
            unit = "pack"
            
        elif "chocolate" in product_name.lower() or "biscuit" in product_name.lower() or "cookie" in product_name.lower():
            # Treats often sold in multi-packs
            if i % 2 == 0:
                quantity = [4, 6, 8][i % 3]
                weight = ["30g", "45g", "50g"][i % 3]
                display_name = f"{variation} {product_name} {quantity}x {weight}".strip()
            else:
                weight = ["100g", "200g", "150g"][i % 3]
                display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Confectionery"
            unit = "pack"
            
        elif "drink" in product_name.lower() or "soda" in product_name.lower() or "juice" in product_name.lower():
            # Drinks sold by volume
            volume = ["330ml", "500ml", "1L", "2L"][i % 4]
            if i % 2 == 0:
                quantity = [4, 6, 8][i % 3]
                display_name = f"{variation} {product_name} {quantity}x {volume}".strip()
            else:
                display_name = f"{variation} {product_name} {volume}".strip()
            product_type = "Beverages"
            unit = "bottle"
            weight = None
            
        else:
            # Default format for other items
            if i % 2 == 0:
                quantity = quantities[i % len(quantities)]
                weight = weights[i % len(weights)]
                display_name = f"{variation} {product_name} {quantity}x {weight}".strip()
            else:
                weight = weights[i % len(weights)]
                display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Groceries"
            unit = units[i % len(units)]
        
        # Use realistic placeholder images
        placeholder_category = product_type.lower().replace(" & ", "-").replace(" ", "-")
        image_url = f"https://placehold.co/400x400/EEE/31343C?text={product_name.replace(' ', '+')}+{variation.replace(' ', '+')}"
        
        results.append({
            "name": display_name,
            "price": prices[i % len(prices)],
            "store": "Tesco",
            "image_url": image_url,
            "category": product_type,
            "weight": weight,
            "quantity": quantity,
            "unit": unit
        })
    
    return results

async def scrape_sainsburys(product_name: str) -> List[Dict[str, Any]]:
    # Mock implementation
    await asyncio.sleep(0.1)
    
    results = []
    variations = ["", "Taste the Difference", "Basics"]
    prices = [1.75, 2.50, 1.20]
    
    for i in range(3):
        variation = variations[i % len(variations)]
        product_type = ""
        display_name = ""
        image_url = ""
        weight = None
        quantity = None
        unit = None
        
        # Format product name based on type
        if "egg" in product_name.lower():
            # Eggs are sold by quantity, not weight
            quantity = [6, 12, 15, 10][i % 4]
            unit = "pack"
            display_name = f"{variation} {product_name} {quantity} {unit}".strip()
            product_type = "Dairy & Eggs"
            weight = None
            
        elif "milk" in product_name.lower():
            # Milk typically sold in volume
            volume = ["1 pint", "2 pints", "4 pints", "6 pints"][i % 4]
            display_name = f"{variation} {product_name} {volume}".strip()
            product_type = "Dairy"
            weight = None
            unit = "bottle"
            
        elif "bread" in product_name.lower():
            # Bread typically sold by loaf
            weight = ["400g", "800g", "600g"][i % 3]
            display_name = f"{variation} {product_name} {weight} loaf".strip()
            product_type = "Bakery"
            unit = "loaf"
            
        elif "apple" in product_name.lower() or "banana" in product_name.lower() or "fruit" in product_name.lower():
            if "apple" in product_name.lower() or "orange" in product_name.lower():
                # Apples/oranges often sold individually or in packs
                quantity = [4, 6, 8][i % 3]
                display_name = f"{variation} {product_name} {quantity} pack".strip()
                unit = "pack"
            else:
                # Other fruit sold by weight
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {weight}".strip()
                unit = "bag"
            product_type = "Produce"
            
        elif "chicken" in product_name.lower() or "beef" in product_name.lower() or "pork" in product_name.lower():
            # Meat sold by weight
            weight = ["500g", "1kg", "250g", "750g"][i % 4]
            display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Meat"
            unit = "package"
            
        elif "pasta" in product_name.lower() or "rice" in product_name.lower():
            # Pasta/rice sold by weight
            weight = ["500g", "1kg", "750g"][i % 3]
            display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Pantry"
            unit = "pack"
            
        elif "chocolate" in product_name.lower() or "biscuit" in product_name.lower() or "cookie" in product_name.lower():
            # Treats often sold in multi-packs
            if i % 2 == 0:
                quantity = [4, 6, 8][i % 3]
                weight = ["30g", "45g", "50g"][i % 3]
                display_name = f"{variation} {product_name} {quantity}x {weight}".strip()
            else:
                weight = ["100g", "200g", "150g"][i % 3]
                display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Confectionery"
            unit = "pack"
            
        elif "drink" in product_name.lower() or "soda" in product_name.lower() or "juice" in product_name.lower():
            # Drinks sold by volume
            volume = ["330ml", "500ml", "1L", "2L"][i % 4]
            if i % 2 == 0:
                quantity = [4, 6, 8][i % 3]
                display_name = f"{variation} {product_name} {quantity}x {volume}".strip()
            else:
                display_name = f"{variation} {product_name} {volume}".strip()
            product_type = "Beverages"
            unit = "bottle"
            weight = None
            
        else:
            # Default format for other items
            if i % 2 == 0:
                quantity = [1, 4, 6, 12][i % 4]
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {quantity}x {weight}".strip()
            else:
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Groceries"
            unit = ["pack", "box", "bag", "carton"][i % 4]
        
        # Use realistic placeholder images with Sainsbury's orange color
        image_url = f"https://placehold.co/400x400/FEBD69/31343C?text={product_name.replace(' ', '+')}+{variation.replace(' ', '+')}"
        
        results.append({
            "name": display_name,
            "price": prices[i % len(prices)],
            "store": "Sainsbury's",
            "image_url": image_url,
            "category": product_type,
            "weight": weight,
            "quantity": quantity,
            "unit": unit
        })
    
    return results

async def scrape_asda(product_name: str) -> List[Dict[str, Any]]:
    # Mock implementation
    await asyncio.sleep(0.1)
    
    results = []
    variations = ["", "Extra Special", "Smart Price"]
    prices = [1.60, 2.80, 1.10]
    
    for i in range(3):
        variation = variations[i % len(variations)]
        product_type = ""
        display_name = ""
        image_url = ""
        weight = None
        quantity = None
        unit = None
        
        # Format product name based on type
        if "egg" in product_name.lower():
            # Eggs are sold by quantity, not weight
            quantity = [6, 12, 15, 10][i % 4]
            unit = "pack"
            display_name = f"{variation} {product_name} {quantity} {unit}".strip()
            product_type = "Dairy & Eggs"
            weight = None
            
        elif "milk" in product_name.lower():
            # Milk typically sold in volume
            volume = ["1 pint", "2 pints", "4 pints", "6 pints"][i % 4]
            display_name = f"{variation} {product_name} {volume}".strip()
            product_type = "Dairy"
            weight = None
            unit = "bottle"
            
        elif "bread" in product_name.lower():
            # Bread typically sold by loaf
            weight = ["400g", "800g", "600g"][i % 3]
            display_name = f"{variation} {product_name} {weight} loaf".strip()
            product_type = "Bakery"
            unit = "loaf"
            
        elif "apple" in product_name.lower() or "banana" in product_name.lower() or "fruit" in product_name.lower():
            if "apple" in product_name.lower() or "orange" in product_name.lower():
                # Apples/oranges often sold individually or in packs
                quantity = [4, 6, 8][i % 3]
                display_name = f"{variation} {product_name} {quantity} pack".strip()
                unit = "pack"
            else:
                # Other fruit sold by weight
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {weight}".strip()
                unit = "bag"
            product_type = "Produce"
            
        elif "chicken" in product_name.lower() or "beef" in product_name.lower() or "pork" in product_name.lower():
            # Meat sold by weight
            weight = ["500g", "1kg", "250g", "750g"][i % 4]
            display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Meat"
            unit = "package"
            
        elif "pasta" in product_name.lower() or "rice" in product_name.lower():
            # Pasta/rice sold by weight
            weight = ["500g", "1kg", "750g"][i % 3]
            display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Pantry"
            unit = "pack"
            
        elif "chocolate" in product_name.lower() or "biscuit" in product_name.lower() or "cookie" in product_name.lower():
            # Treats often sold in multi-packs
            if i % 2 == 0:
                quantity = [4, 6, 8][i % 3]
                weight = ["30g", "45g", "50g"][i % 3]
                display_name = f"{variation} {product_name} {quantity}x {weight}".strip()
            else:
                weight = ["100g", "200g", "150g"][i % 3]
                display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Confectionery"
            unit = "pack"
            
        elif "drink" in product_name.lower() or "soda" in product_name.lower() or "juice" in product_name.lower():
            # Drinks sold by volume
            volume = ["330ml", "500ml", "1L", "2L"][i % 4]
            if i % 2 == 0:
                quantity = [4, 6, 8][i % 3]
                display_name = f"{variation} {product_name} {quantity}x {volume}".strip()
            else:
                display_name = f"{variation} {product_name} {volume}".strip()
            product_type = "Beverages"
            unit = "bottle"
            weight = None
            
        else:
            # Default format for other items
            if i % 2 == 0:
                quantity = [1, 4, 6, 12][i % 4]
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {quantity}x {weight}".strip()
            else:
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Groceries"
            unit = ["pack", "box", "bag", "carton"][i % 4]
        
        # Use realistic placeholder images with Asda green color
        image_url = f"https://placehold.co/400x400/78BE20/FFFFFF?text={product_name.replace(' ', '+')}+{variation.replace(' ', '+')}"
        
        results.append({
            "name": display_name,
            "price": prices[i % len(prices)],
            "store": "Asda",
            "image_url": image_url,
            "category": product_type,
            "weight": weight,
            "quantity": quantity,
            "unit": unit
        })
    
    return results

async def scrape_morrisons(product_name: str) -> List[Dict[str, Any]]:
    # Mock implementation
    await asyncio.sleep(0.1)
    
    results = []
    variations = ["", "The Best", "Savers"]
    prices = [1.80, 2.95, 1.25]
    
    for i in range(3):
        variation = variations[i % len(variations)]
        product_type = ""
        display_name = ""
        image_url = ""
        weight = None
        quantity = None
        unit = None
        
        # Format product name based on type
        if "egg" in product_name.lower():
            # Eggs are sold by quantity, not weight
            quantity = [6, 12, 15, 10][i % 4]
            unit = "pack"
            display_name = f"{variation} {product_name} {quantity} {unit}".strip()
            product_type = "Dairy & Eggs"
            weight = None
            
        elif "milk" in product_name.lower():
            # Milk typically sold in volume
            volume = ["1 pint", "2 pints", "4 pints", "6 pints"][i % 4]
            display_name = f"{variation} {product_name} {volume}".strip()
            product_type = "Dairy"
            weight = None
            unit = "bottle"
            
        elif "bread" in product_name.lower():
            # Bread typically sold by loaf
            weight = ["400g", "800g", "600g"][i % 3]
            display_name = f"{variation} {product_name} {weight} loaf".strip()
            product_type = "Bakery"
            unit = "loaf"
            
        elif "apple" in product_name.lower() or "banana" in product_name.lower() or "fruit" in product_name.lower():
            if "apple" in product_name.lower() or "orange" in product_name.lower():
                # Apples/oranges often sold individually or in packs
                quantity = [4, 6, 8][i % 3]
                display_name = f"{variation} {product_name} {quantity} pack".strip()
                unit = "pack"
            else:
                # Other fruit sold by weight
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {weight}".strip()
                unit = "bag"
            product_type = "Produce"
            
        elif "chicken" in product_name.lower() or "beef" in product_name.lower() or "pork" in product_name.lower():
            # Meat sold by weight
            weight = ["500g", "1kg", "250g", "750g"][i % 4]
            display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Meat"
            unit = "package"
            
        elif "pasta" in product_name.lower() or "rice" in product_name.lower():
            # Pasta/rice sold by weight
            weight = ["500g", "1kg", "750g"][i % 3]
            display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Pantry"
            unit = "pack"
            
        elif "chocolate" in product_name.lower() or "biscuit" in product_name.lower() or "cookie" in product_name.lower():
            # Treats often sold in multi-packs
            if i % 2 == 0:
                quantity = [4, 6, 8][i % 3]
                weight = ["30g", "45g", "50g"][i % 3]
                display_name = f"{variation} {product_name} {quantity}x {weight}".strip()
            else:
                weight = ["100g", "200g", "150g"][i % 3]
                display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Confectionery"
            unit = "pack"
            
        elif "drink" in product_name.lower() or "soda" in product_name.lower() or "juice" in product_name.lower():
            # Drinks sold by volume
            volume = ["330ml", "500ml", "1L", "2L"][i % 4]
            if i % 2 == 0:
                quantity = [4, 6, 8][i % 3]
                display_name = f"{variation} {product_name} {quantity}x {volume}".strip()
            else:
                display_name = f"{variation} {product_name} {volume}".strip()
            product_type = "Beverages"
            unit = "bottle"
            weight = None
            
        else:
            # Default format for other items
            if i % 2 == 0:
                quantity = [1, 4, 6, 12][i % 4]
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {quantity}x {weight}".strip()
            else:
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Groceries"
            unit = ["pack", "box", "bag", "carton"][i % 4]
        
        # Use realistic placeholder images with Morrisons yellow color
        image_url = f"https://placehold.co/400x400/FFBB00/000000?text={product_name.replace(' ', '+')}+{variation.replace(' ', '+')}"
        
        results.append({
            "name": display_name,
            "price": prices[i % len(prices)],
            "store": "Morrisons",
            "image_url": image_url,
            "category": product_type,
            "weight": weight,
            "quantity": quantity,
            "unit": unit
        })
    
    return results

async def scrape_aldi(product_name: str) -> List[Dict[str, Any]]:
    # Mock implementation
    await asyncio.sleep(0.1)
    
    results = []
    variations = ["", "Specially Selected"]
    prices = [1.30, 2.30]
    
    for i in range(2):
        variation = variations[i % len(variations)]
        product_type = ""
        display_name = ""
        image_url = ""
        weight = None
        quantity = None
        unit = None
        
        # Format product name based on type
        if "egg" in product_name.lower():
            # Eggs are sold by quantity, not weight
            quantity = [6, 12, 15, 10][i % 4]
            unit = "pack"
            display_name = f"{variation} {product_name} {quantity} {unit}".strip()
            product_type = "Dairy & Eggs"
            weight = None
            
        elif "milk" in product_name.lower():
            # Milk typically sold in volume
            volume = ["1 pint", "2 pints", "4 pints", "6 pints"][i % 4]
            display_name = f"{variation} {product_name} {volume}".strip()
            product_type = "Dairy"
            weight = None
            unit = "bottle"
            
        elif "bread" in product_name.lower():
            # Bread typically sold by loaf
            weight = ["400g", "800g", "600g"][i % 3]
            display_name = f"{variation} {product_name} {weight} loaf".strip()
            product_type = "Bakery"
            unit = "loaf"
            
        elif "apple" in product_name.lower() or "banana" in product_name.lower() or "fruit" in product_name.lower():
            if "apple" in product_name.lower() or "orange" in product_name.lower():
                # Apples/oranges often sold individually or in packs
                quantity = [4, 6, 8][i % 3]
                display_name = f"{variation} {product_name} {quantity} pack".strip()
                unit = "pack"
            else:
                # Other fruit sold by weight
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {weight}".strip()
                unit = "bag"
            product_type = "Produce"
            
        elif "chicken" in product_name.lower() or "beef" in product_name.lower() or "pork" in product_name.lower():
            # Meat sold by weight
            weight = ["500g", "1kg", "250g", "750g"][i % 4]
            display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Meat"
            unit = "package"
            
        elif "pasta" in product_name.lower() or "rice" in product_name.lower():
            # Pasta/rice sold by weight
            weight = ["500g", "1kg", "750g"][i % 3]
            display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Pantry"
            unit = "pack"
            
        elif "chocolate" in product_name.lower() or "biscuit" in product_name.lower() or "cookie" in product_name.lower():
            # Treats often sold in multi-packs
            if i % 2 == 0:
                quantity = [4, 6, 8][i % 3]
                weight = ["30g", "45g", "50g"][i % 3]
                display_name = f"{variation} {product_name} {quantity}x {weight}".strip()
            else:
                weight = ["100g", "200g", "150g"][i % 3]
                display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Confectionery"
            unit = "pack"
            
        elif "drink" in product_name.lower() or "soda" in product_name.lower() or "juice" in product_name.lower():
            # Drinks sold by volume
            volume = ["330ml", "500ml", "1L", "2L"][i % 4]
            if i % 2 == 0:
                quantity = [4, 6, 8][i % 3]
                display_name = f"{variation} {product_name} {quantity}x {volume}".strip()
            else:
                display_name = f"{variation} {product_name} {volume}".strip()
            product_type = "Beverages"
            unit = "bottle"
            weight = None
            
        else:
            # Default format for other items
            if i % 2 == 0:
                quantity = [1, 4, 6, 12][i % 4]
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {quantity}x {weight}".strip()
            else:
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Groceries"
            unit = ["pack", "box", "bag", "carton"][i % 4]
        
        # Use realistic placeholder images with Aldi blue color
        image_url = f"https://placehold.co/400x400/1D428A/FFFFFF?text={product_name.replace(' ', '+')}+{variation.replace(' ', '+')}"
        
        results.append({
            "name": display_name,
            "price": prices[i % len(prices)],
            "store": "Aldi",
            "image_url": image_url,
            "category": product_type,
            "weight": weight,
            "quantity": quantity,
            "unit": unit
        })
    
    return results

async def scrape_lidl(product_name: str) -> List[Dict[str, Any]]:
    # Mock implementation
    await asyncio.sleep(0.1)
    
    results = []
    variations = ["", "Deluxe"]
    prices = [1.20, 2.20]
    
    for i in range(2):
        variation = variations[i % len(variations)]
        product_type = ""
        display_name = ""
        image_url = ""
        weight = None
        quantity = None
        unit = None
        
        # Format product name based on type
        if "egg" in product_name.lower():
            # Eggs are sold by quantity, not weight
            quantity = [6, 12, 15, 10][i % 4]
            unit = "pack"
            display_name = f"{variation} {product_name} {quantity} {unit}".strip()
            product_type = "Dairy & Eggs"
            weight = None
            
        elif "milk" in product_name.lower():
            # Milk typically sold in volume
            volume = ["1 pint", "2 pints", "4 pints", "6 pints"][i % 4]
            display_name = f"{variation} {product_name} {volume}".strip()
            product_type = "Dairy"
            weight = None
            unit = "bottle"
            
        elif "bread" in product_name.lower():
            # Bread typically sold by loaf
            weight = ["400g", "800g", "600g"][i % 3]
            display_name = f"{variation} {product_name} {weight} loaf".strip()
            product_type = "Bakery"
            unit = "loaf"
            
        elif "apple" in product_name.lower() or "banana" in product_name.lower() or "fruit" in product_name.lower():
            if "apple" in product_name.lower() or "orange" in product_name.lower():
                # Apples/oranges often sold individually or in packs
                quantity = [4, 6, 8][i % 3]
                display_name = f"{variation} {product_name} {quantity} pack".strip()
                unit = "pack"
            else:
                # Other fruit sold by weight
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {weight}".strip()
                unit = "bag"
            product_type = "Produce"
            
        elif "chicken" in product_name.lower() or "beef" in product_name.lower() or "pork" in product_name.lower():
            # Meat sold by weight
            weight = ["500g", "1kg", "250g", "750g"][i % 4]
            display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Meat"
            unit = "package"
            
        elif "pasta" in product_name.lower() or "rice" in product_name.lower():
            # Pasta/rice sold by weight
            weight = ["500g", "1kg", "750g"][i % 3]
            display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Pantry"
            unit = "pack"
            
        elif "chocolate" in product_name.lower() or "biscuit" in product_name.lower() or "cookie" in product_name.lower():
            # Treats often sold in multi-packs
            if i % 2 == 0:
                quantity = [4, 6, 8][i % 3]
                weight = ["30g", "45g", "50g"][i % 3]
                display_name = f"{variation} {product_name} {quantity}x {weight}".strip()
            else:
                weight = ["100g", "200g", "150g"][i % 3]
                display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Confectionery"
            unit = "pack"
            
        elif "drink" in product_name.lower() or "soda" in product_name.lower() or "juice" in product_name.lower():
            # Drinks sold by volume
            volume = ["330ml", "500ml", "1L", "2L"][i % 4]
            if i % 2 == 0:
                quantity = [4, 6, 8][i % 3]
                display_name = f"{variation} {product_name} {quantity}x {volume}".strip()
            else:
                display_name = f"{variation} {product_name} {volume}".strip()
            product_type = "Beverages"
            unit = "bottle"
            weight = None
            
        else:
            # Default format for other items
            if i % 2 == 0:
                quantity = [1, 4, 6, 12][i % 4]
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {quantity}x {weight}".strip()
            else:
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Groceries"
            unit = ["pack", "box", "bag", "carton"][i % 4]
        
        # Use realistic placeholder images with Lidl blue color
        image_url = f"https://placehold.co/400x400/0050AA/FFFFFF?text={product_name.replace(' ', '+')}+{variation.replace(' ', '+')}"
        
        results.append({
            "name": display_name,
            "price": prices[i % len(prices)],
            "store": "Lidl",
            "image_url": image_url,
            "category": product_type,
            "weight": weight,
            "quantity": quantity,
            "unit": unit
        })
    
    return results

async def scrape_waitrose(product_name: str) -> List[Dict[str, Any]]:
    # Mock implementation
    await asyncio.sleep(0.1)
    
    results = []
    variations = ["", "Duchy Organic", "Essential"]
    prices = [2.25, 3.50, 1.90]
    
    for i in range(3):
        variation = variations[i % len(variations)]
        name = f"{variation} {product_name}".strip()
        results.append({
            "name": name,
            "price": prices[i % len(prices)],
            "store": "Waitrose",
            "image_url": f"https://example.com/waitrose/{product_name.replace(' ', '_')}_{i}.jpg",
            "category": "Groceries"
        })
    
    return results

async def scrape_coop(product_name: str) -> List[Dict[str, Any]]:
    # Mock implementation
    await asyncio.sleep(0.1)
    
    results = []
    variations = ["", "Irresistible"]
    prices = [1.85, 2.75]
    
    for i in range(2):
        variation = variations[i % len(variations)]
        name = f"{variation} {product_name}".strip()
        results.append({
            "name": name,
            "price": prices[i % len(prices)],
            "store": "Co-op",
            "image_url": f"https://example.com/coop/{product_name.replace(' ', '_')}_{i}.jpg",
            "category": "Groceries"
        })
    
    return results

async def scrape_marks_spencer(product_name: str) -> List[Dict[str, Any]]:
    # Mock implementation
    await asyncio.sleep(0.1)
    
    results = []
    variations = ["", "Luxury", "M&S Collection"]
    prices = [2.50, 3.95, 2.95]
    
    for i in range(3):
        variation = variations[i % len(variations)]
        name = f"{variation} {product_name}".strip()
        results.append({
            "name": name,
            "price": prices[i % len(prices)],
            "store": "M&S",
            "image_url": f"https://example.com/marks_spencer/{product_name.replace(' ', '_')}_{i}.jpg",
            "category": "Groceries"
        })
    
    return results

async def scrape_iceland(product_name: str) -> List[Dict[str, Any]]:
    # Mock implementation
    await asyncio.sleep(0.1)
    
    results = []
    variations = ["", "Luxury"]
    prices = [1.40, 2.40]
    
    for i in range(2):
        variation = variations[i % len(variations)]
        name = f"{variation} {product_name}".strip()
        results.append({
            "name": name,
            "price": prices[i % len(prices)],
            "store": "Iceland",
            "image_url": f"https://example.com/iceland/{product_name.replace(' ', '_')}_{i}.jpg",
            "category": "Groceries"
        })
    
    return results

async def scrape_amazon(product_name: str) -> List[Dict[str, Any]]:
    # Mock implementation
    await asyncio.sleep(0.1)
    
    results = []
    variations = ["", "Amazon Fresh", "Amazon Basics", "Amazon Choice"]
    prices = [1.90, 2.95, 1.50, 3.50]
    
    for i in range(3):
        variation = variations[i % len(variations)]
        product_type = ""
        display_name = ""
        image_url = ""
        weight = None
        quantity = None
        unit = None
        
        # Format product name based on type
        if "egg" in product_name.lower():
            # Eggs are sold by quantity, not weight
            quantity = [6, 12, 15, 10][i % 4]
            unit = "pack"
            display_name = f"{variation} {product_name} {quantity} {unit}".strip()
            product_type = "Dairy & Eggs"
            weight = None
            
        elif "milk" in product_name.lower():
            # Milk typically sold in volume
            volume = ["1 pint", "2 pints", "4 pints", "6 pints"][i % 4]
            display_name = f"{variation} {product_name} {volume}".strip()
            product_type = "Dairy"
            weight = None
            unit = "bottle"
            
        elif "bread" in product_name.lower():
            # Bread typically sold by loaf
            weight = ["400g", "800g", "600g"][i % 3]
            display_name = f"{variation} {product_name} {weight} loaf".strip()
            product_type = "Bakery"
            unit = "loaf"
            
        elif "apple" in product_name.lower() or "banana" in product_name.lower() or "fruit" in product_name.lower():
            if "apple" in product_name.lower() or "orange" in product_name.lower():
                # Apples/oranges often sold individually or in packs
                quantity = [4, 6, 8][i % 3]
                display_name = f"{variation} {product_name} {quantity} pack".strip()
                unit = "pack"
            else:
                # Other fruit sold by weight
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {weight}".strip()
                unit = "bag"
            product_type = "Produce"
            
        elif "chicken" in product_name.lower() or "beef" in product_name.lower() or "pork" in product_name.lower():
            # Meat sold by weight
            weight = ["500g", "1kg", "250g", "750g"][i % 4]
            display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Meat"
            unit = "package"
            
        elif "pasta" in product_name.lower() or "rice" in product_name.lower():
            # Pasta/rice sold by weight
            weight = ["500g", "1kg", "750g"][i % 3]
            display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Pantry"
            unit = "pack"
            
        elif "chocolate" in product_name.lower() or "biscuit" in product_name.lower() or "cookie" in product_name.lower():
            # Treats often sold in multi-packs
            if i % 2 == 0:
                quantity = [4, 6, 8][i % 3]
                weight = ["30g", "45g", "50g"][i % 3]
                display_name = f"{variation} {product_name} {quantity}x {weight}".strip()
            else:
                weight = ["100g", "200g", "150g"][i % 3]
                display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Confectionery"
            unit = "pack"
            
        elif "drink" in product_name.lower() or "soda" in product_name.lower() or "juice" in product_name.lower():
            # Drinks sold by volume
            volume = ["330ml", "500ml", "1L", "2L"][i % 4]
            if i % 2 == 0:
                quantity = [4, 6, 8][i % 3]
                display_name = f"{variation} {product_name} {quantity}x {volume}".strip()
            else:
                display_name = f"{variation} {product_name} {volume}".strip()
            product_type = "Beverages"
            unit = "bottle"
            weight = None
            
        else:
            # Default format for other items
            if i % 2 == 0:
                quantity = [1, 4, 6, 12][i % 4]
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {quantity}x {weight}".strip()
            else:
                weight = ["500g", "1kg", "250g", "750g"][i % 4]
                display_name = f"{variation} {product_name} {weight}".strip()
            product_type = "Groceries"
            unit = ["pack", "box", "bag", "carton"][i % 4]
        
        # Use realistic placeholder images with Amazon colors
        image_url = f"https://placehold.co/400x400/232F3E/FFFFFF?text={product_name.replace(' ', '+')}+{variation.replace(' ', '+')}"
        
        results.append({
            "name": display_name,
            "price": prices[i % len(prices)],
            "store": "Amazon",
            "image_url": image_url,
            "category": product_type,
            "weight": weight,
            "quantity": quantity,
            "unit": unit
        })
    
    return results

# Function map for dynamic calling
scraper_functions = {
    "scrape_tesco": scrape_tesco,
    "scrape_sainsburys": scrape_sainsburys,
    "scrape_asda": scrape_asda,
    "scrape_morrisons": scrape_morrisons,
    "scrape_aldi": scrape_aldi,
    "scrape_lidl": scrape_lidl,
    "scrape_waitrose": scrape_waitrose,
    "scrape_coop": scrape_coop,
    "scrape_marks_spencer": scrape_marks_spencer,
    "scrape_iceland": scrape_iceland,
    "scrape_amazon": scrape_amazon
}

# Background Task Functions
async def update_prices():
    """Background task to update prices periodically"""
    logging.info("Updating product prices...")
    products = await db.products.find().to_list(1000)
    
    for product in products:
        for retailer in UK_GROCERY_RETAILERS:
            scraper_func = scraper_functions.get(retailer["scraper_function"])
            if scraper_func:
                try:
                    results = await scraper_func(product["name"])
                    if results:
                        # Update price for the first match
                        price_data = {
                            "product_id": product["id"],
                            "store": retailer["name"],
                            "price": results[0]["price"],
                            "created_at": datetime.utcnow()
                        }
                        await db.prices.insert_one(price_data)
                except Exception as e:
                    logging.error(f"Error updating price for {product['name']} from {retailer['name']}: {str(e)}")

# API Routes
@api_router.post("/register", response_model=User)
async def register_user(user: UserCreate):
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    user_data = UserInDB(
        email=user.email,
        name=user.name,
        hashed_password=hashed_password
    )
    
    # Insert into database
    user_dict = user_data.model_dump()
    await db.users.insert_one(user_dict)
    
    # Return user without hashed password
    return User(id=user_data.id, email=user_data.email, name=user_data.name, created_at=user_data.created_at)

@api_router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@api_router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@api_router.get("/search", response_model=SearchResponse)
async def search_products(query: str, current_user: User = Depends(get_current_user)):
    # Search for existing products in the database
    products_cursor = db.products.find({"name": {"$regex": query, "$options": "i"}})
    products = await products_cursor.to_list(20)
    
    if not products:
        # If no products found, scrape all retailers
        all_results = []
        for retailer in UK_GROCERY_RETAILERS:
            scraper_func = scraper_functions.get(retailer["scraper_function"])
            if scraper_func:
                try:
                    results = await scraper_func(query)
                    all_results.extend(results)
                except Exception as e:
                    logging.error(f"Error scraping {retailer['name']}: {str(e)}")
        
        # Create unique products from results
        unique_names = set()
        unique_products = []
        
        for result in all_results:
            if result["name"] not in unique_names:
                unique_names.add(result["name"])
                
                # Create and save product
                product = Product(
                    name=result["name"],
                    category=result["category"],
                    image_url=result["image_url"],
                    weight=result.get("weight"),
                    quantity=result.get("quantity"),
                    unit=result.get("unit")
                )
                product_dict = product.model_dump()
                await db.products.insert_one(product_dict)
                unique_products.append(product)
                
                # Save price
                price = Price(
                    product_id=product.id,
                    store=result["store"],
                    price=result["price"]
                )
                price_dict = price.model_dump()
                await db.prices.insert_one(price_dict)
        
        products = [p.model_dump() for p in unique_products]
    
    # Get prices for all products
    product_ids = [product["id"] for product in products]
    prices_cursor = db.prices.find({"product_id": {"$in": product_ids}})
    prices = await prices_cursor.to_list(100)
    
    # Group prices by product_id
    prices_by_product = {}
    for price in prices:
        product_id = price["product_id"]
        if product_id not in prices_by_product:
            prices_by_product[product_id] = []
        prices_by_product[product_id].append(Price(**price))
    
    return {"products": [Product(**p) for p in products], "prices": prices_by_product}

@api_router.get("/stores", response_model=List[StoreInfo])
async def get_stores():
    return [StoreInfo(name=store["name"], url=store["url"]) for store in UK_GROCERY_RETAILERS]

@api_router.post("/shopping-lists", response_model=ShoppingList)
async def create_shopping_list(shopping_list: ShoppingListCreate, current_user: User = Depends(get_current_user)):
    # Ensure user is creating their own shopping list
    if shopping_list.user_id != current_user.id:
        # Instead of raising an error, use the current user's ID
        shopping_list.user_id = current_user.id
    
    # Create shopping list
    new_list = ShoppingList(
        name=shopping_list.name,
        user_id=shopping_list.user_id,
        items=[ShoppingListItem(**item.model_dump()) for item in shopping_list.items]
    )
    
    # Save to database
    list_dict = new_list.model_dump()
    await db.shopping_lists.insert_one(list_dict)
    
    return new_list

@api_router.get("/shopping-lists", response_model=List[ShoppingList])
async def get_user_shopping_lists(current_user: User = Depends(get_current_user)):
    lists_cursor = db.shopping_lists.find({"user_id": current_user.id})
    lists = await lists_cursor.to_list(100)
    return [ShoppingList(**list_data) for list_data in lists]

@api_router.get("/shopping-lists/{list_id}", response_model=ShoppingList)
async def get_shopping_list(list_id: str, current_user: User = Depends(get_current_user)):
    shopping_list = await db.shopping_lists.find_one({"id": list_id})
    
    if not shopping_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shopping list not found"
        )
    
    # Check ownership
    if shopping_list["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this shopping list"
        )
    
    return ShoppingList(**shopping_list)

@api_router.put("/shopping-lists/{list_id}", response_model=ShoppingList)
async def update_shopping_list(list_id: str, updated_list: ShoppingListCreate, current_user: User = Depends(get_current_user)):
    # Check if list exists
    existing_list = await db.shopping_lists.find_one({"id": list_id})
    if not existing_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shopping list not found"
        )
    
    # Check ownership
    if existing_list["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this shopping list"
        )
    
    # Update the list
    updated_data = ShoppingList(
        id=list_id,
        name=updated_list.name,
        user_id=current_user.id,
        created_at=existing_list["created_at"],
        updated_at=datetime.utcnow(),
        items=[ShoppingListItem(**item.model_dump()) for item in updated_list.items]
    )
    
    await db.shopping_lists.replace_one({"id": list_id}, updated_data.model_dump())
    
    return updated_data

@api_router.delete("/shopping-lists/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shopping_list(list_id: str, current_user: User = Depends(get_current_user)):
    # Check if list exists
    existing_list = await db.shopping_lists.find_one({"id": list_id})
    if not existing_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shopping list not found"
        )
    
    # Check ownership
    if existing_list["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this shopping list"
        )
    
    # Delete the list
    await db.shopping_lists.delete_one({"id": list_id})
    
    return None

# Root API routes
@api_router.get("/guest-search", response_model=SearchResponse)
async def guest_search_products(query: str):
    """
    Public endpoint for searching products without authentication.
    """
    # Search for existing products in the database
    products_cursor = db.products.find({"name": {"$regex": query, "$options": "i"}})
    products = await products_cursor.to_list(20)
    
    if not products:
        # If no products found, scrape all retailers
        all_results = []
        for retailer in UK_GROCERY_RETAILERS:
            scraper_func = scraper_functions.get(retailer["scraper_function"])
            if scraper_func:
                try:
                    results = await scraper_func(query)
                    all_results.extend(results)
                except Exception as e:
                    logging.error(f"Error scraping {retailer['name']}: {str(e)}")
        
        # Create unique products from results
        unique_names = set()
        unique_products = []
        
        for result in all_results:
            if result["name"] not in unique_names:
                unique_names.add(result["name"])
                
                # Create and save product
                product = Product(
                    name=result["name"],
                    category=result["category"],
                    image_url=result["image_url"],
                    weight=result.get("weight"),
                    quantity=result.get("quantity"),
                    unit=result.get("unit")
                )
                product_dict = product.model_dump()
                await db.products.insert_one(product_dict)
                unique_products.append(product)
                
                # Save price
                price = Price(
                    product_id=product.id,
                    store=result["store"],
                    price=result["price"]
                )
                price_dict = price.model_dump()
                await db.prices.insert_one(price_dict)
        
        products = [p.model_dump() for p in unique_products]
    
    # Get prices for all products
    product_ids = [product["id"] for product in products]
    prices_cursor = db.prices.find({"product_id": {"$in": product_ids}})
    prices = await prices_cursor.to_list(100)
    
    # Group prices by product_id
    prices_by_product = {}
    for price in prices:
        product_id = price["product_id"]
        if product_id not in prices_by_product:
            prices_by_product[product_id] = []
        prices_by_product[product_id].append(Price(**price))
    
    return {"products": [Product(**p) for p in products], "prices": prices_by_product}

@api_router.get("/")
async def root():
    return {"message": "UK Grocery Price Comparison API"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Schedule periodic price updates
scheduler.add_job(
    update_prices,
    trigger=IntervalTrigger(hours=12),
    id="price_update_job",
    replace_existing=True
)

@app.on_event("startup")
async def startup_event():
    # Start the scheduler
    scheduler.start()
    logger.info("APScheduler started")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
    # Shut down the scheduler
    scheduler.shutdown()
    logger.info("APScheduler shut down")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)

