import psycopg2
from psycopg2.extras import DictCursor
from typing import List, Dict, Any, Optional

from eCombat.src.config.settings import postgres_dsn

def _get_connection():
    return psycopg2.connect(dsn=postgres_dsn())

def search_products(
    query: Optional[str] = None,
    category: Optional[str] = None,
    max_price: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Search the electronics product catalog.
    
    Args:
        query: Part of the product name or description to filter by.
        category: Exact category to filter by (e.g. 'Smartphones', 'Laptops', 'Audio', 'Wearables', 'Smart Home').
        max_price: Maximum price filter.
        
    Returns:
        A list of matching products, each with keys: id, name, description, price, stock_quantity, category.
    """
    conn = _get_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    try:
        sql = "SELECT id, name, description, price, stock_quantity, category FROM products WHERE 1=1"
        params = []
        
        if query:
            sql += " AND (name ILIKE %s OR description ILIKE %s)"
            params.extend([f"%{query}%", f"%{query}%"])
        if category:
            sql += " AND category = %s"
            params.append(category)
        if max_price is not None:
            sql += " AND price <= %s"
            params.append(max_price)
            
        sql += " ORDER BY price ASC;"
        cursor.execute(sql, params)
        
        results = [dict(row) for row in cursor.fetchall()]
        # Convert numeric Decimal price to float for easy json serialization
        for r in results:
            r['price'] = float(r['price'])
        return results
    finally:
        cursor.close()
        conn.close()

def place_order(
    customer_name: str,
    product_name: str,
    quantity: int
) -> Dict[str, Any]:
    """
    Place a new customer order for an electronics product.
    
    Args:
        customer_name: The full name of the customer placing the order.
        product_name: The exact name of the product to purchase (e.g., 'iPhone 15 Pro Max').
        quantity: The quantity to buy. Must be greater than 0.
        
    Returns:
        A dictionary with the order details or an error message if stock is insufficient or the product is not found.
    """
    if quantity <= 0:
        return {"error": "Quantity must be greater than 0."}
        
    conn = _get_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    try:
        # Check product existence and stock
        cursor.execute("SELECT id, name, price, stock_quantity FROM products WHERE name = %s;", (product_name,))
        product = cursor.fetchone()
        if not product:
            return {"error": f"Product '{product_name}' not found."}
            
        product_id, name, price, stock_quantity = product['id'], product['name'], product['price'], product['stock_quantity']
        if stock_quantity < quantity:
            return {"error": f"Insufficient stock. Only {stock_quantity} units available."}
            
        total_price = float(price) * quantity
        
        # Deduct stock
        cursor.execute("UPDATE products SET stock_quantity = stock_quantity - %s WHERE id = %s;", (quantity, product_id))
        
        # Create order
        cursor.execute("""
            INSERT INTO orders (customer_name, product_id, quantity, total_price, status)
            VALUES (%s, %s, %s, %s, 'Pending')
            RETURNING id, status, order_date;
        """, (customer_name, product_id, quantity, total_price))
        
        order = cursor.fetchone()
        conn.commit()
        
        return {
            "order_id": order['id'],
            "customer_name": customer_name,
            "product_name": product_name,
            "quantity": quantity,
            "total_price": total_price,
            "status": order['status'],
            "order_date": str(order['order_date'])
        }
    except Exception as e:
        conn.rollback()
        return {"error": f"Failed to place order: {str(e)}"}
    finally:
        cursor.close()
        conn.close()

def get_order_status(order_id: int) -> Dict[str, Any]:
    """
    Retrieve the status and details of an existing order.
    
    Args:
        order_id: The unique ID of the order.
        
    Returns:
        A dictionary with order information, or an error if not found.
    """
    conn = _get_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    try:
        cursor.execute("""
            SELECT o.id, o.customer_name, p.name as product_name, o.quantity, o.total_price, o.status, o.order_date
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.id = %s;
        """, (order_id,))
        order = cursor.fetchone()
        if not order:
            return {"error": f"Order #{order_id} not found."}
            
        res = dict(order)
        res['total_price'] = float(res['total_price'])
        res['order_date'] = str(res['order_date'])
        return res
    finally:
        cursor.close()
        conn.close()

def log_session_interaction(
    session_id: str,
    user_query: str,
    agent_response: str
) -> Dict[str, Any]:
    """
    Log user queries and agent responses in session history.
    
    Args:
        session_id: Unique session identifier.
        user_query: The customer's message.
        agent_response: The agent's final answer.
        
    Returns:
        A status message indicating success or failure.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO session_history (session_id, user_query, agent_response)
            VALUES (%s, %s, %s);
        """, (session_id, user_query, agent_response))
        conn.commit()
        return {"status": "Success", "message": "Interaction logged."}
    except Exception as e:
        conn.rollback()
        return {"status": "Error", "message": str(e)}
    finally:
        cursor.close()
        conn.close()
