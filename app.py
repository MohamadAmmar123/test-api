from datetime import datetime
from typing import Any
from flask import Flask, render_template, request
from flask_cors import CORS
import sqlite3

app: Flask = Flask(__name__)
CORS(app)

@app.get("/")
def status() -> str:
    return render_template('status.html')

@app.get("/rooms")
def rooms() -> dict[str, Any]:
    with sqlite3.connect("data.db") as con:
        try:
            cur: sqlite3.Cursor = con.cursor()
            result: sqlite3.Cursor = cur.execute(
                "SELECT r.ID, r.NAME, t.NAME, t.PRICE FROM ROOMS r INNER JOIN ROOM_TYPE t ON r.ROOM_TYPE = t.ID;")
            data: list[dict[str, Any]] = list(map(
                    lambda row: {
                        "id": row[0],
                        "name": row[1],
                        "type": row[2],
                        "price": row[3]
                    },
                    result.fetchall()
            ))

            return {
                "data": data
            }
        except:
            return {
                "data": {},
                "status": "ERROR - Execution failed."
            }
    
@app.post("/check")
def check() -> dict[str, Any]:
    room_type: int = -1
    room_amount: int = 0
    checkin_date: datetime = None
    checkout_date: datetime = None
    is_available: str = "NOT AVAILABLE"

    try:
        room_type = request.json["type"]
        room_amount = request.json["amount"]
        checkin_date = request.json["checkin"]
        checkout_date = request.json["checkout"]
    except:
        return {
            "data": {},
            "status": "ERROR - Not enough data."
        }

    with sqlite3.connect("data.db") as con:
        try:
            cur: sqlite3.Cursor = con.cursor()
            result: sqlite3.Cursor = cur.execute(
                """
                SELECT
                    COUNT(ID) AS VACANT
                FROM ROOMS
                WHERE
                    ROOM_TYPE = :type AND
                    datetime(:in) > datetime(:now) AND
                    ID NOT IN (
                    SELECT br.ROOM_ID
                    FROM BOOKED_ROOMS br
                    LEFT JOIN ROOMS r
                    ON br.ROOM_ID = r.ID
                    LEFT JOIN BOOKINGS b
                    ON br.BOOKING_ID = b.ID
                    WHERE
                        r.ROOM_TYPE = :type AND (
                        datetime(b.CHECKIN) BETWEEN datetime(:in) AND datetime(:out) OR
                        datetime(b.CHECKOUT) BETWEEN datetime(:in) AND datetime(:out)
                    )
                );
                """,
                {
                    "type": room_type, "in": checkin_date, "out": checkout_date, "now": datetime.now().isoformat()
                }
            )

            data: sqlite3.Cursor = result.fetchone()
            print(data[0])

            if data[0] >= room_amount:
                is_available = "AVAILABLE"
            else:
                is_available = "NOT AVAILABLE"
            
            return {
                "data": {
                    "available": is_available
                }
            }
        
        except:
            return {
                "data": {},
                "status": "ERROR - Execution failed."
            }

@app.post("/book")
def book() -> dict[str, Any]:
    room_type: int = -1
    room_amount: int = 0
    email: str = ""
    name: str = ""
    checkin_date: datetime = None
    checkout_date: datetime = None

    try:
        room_type = request.json["type"]
        room_amount = request.json["amount"]
        email = request.json["email"]
        name = request.json["name"]
        checkin_date = request.json["checkin"]
        checkout_date = request.json["checkout"]
    except:
        return {
            "data": {},
            "status": "ERROR - Not enough data."
        }

    with sqlite3.connect("data.db") as con:
        try:
            cur: sqlite3.Cursor = con.cursor()
            vacant: sqlite3.Cursor = cur.execute(
                """
                SELECT
                    r.ID, t.PRICE
                FROM ROOMS r
                INNER JOIN ROOM_TYPE t
                ON r.ROOM_TYPE = t.ID
                WHERE
                    r.ROOM_TYPE = :type AND
                    datetime(:in) > datetime(:now) AND
                    r.ID NOT IN (
                    SELECT br.ROOM_ID
                    FROM BOOKED_ROOMS br
                    LEFT JOIN ROOMS r
                    ON br.ROOM_ID = r.ID
                    LEFT JOIN BOOKINGS b
                    ON br.BOOKING_ID = b.ID
                    WHERE
                        r.ROOM_TYPE = :type AND (
                        datetime(b.CHECKIN) BETWEEN datetime(:in) AND datetime(:out) OR
                        datetime(b.CHECKOUT) BETWEEN datetime(:in) AND datetime(:out)
                    )
                )
                ORDER BY r.ID ASC
                LIMIT :amount;
                """,
                {
                    "type": room_type, "in": checkin_date, "out": checkout_date, "now": datetime.now().isoformat(), "amount": room_amount
                }
            )

            rooms: list[list[Any]] = vacant.fetchall()

            if len(rooms) >= room_amount:
                args: dict[str, Any] = {
                    "email": email,
                    "name": name,
                    "in": checkin_date,
                    "out": checkout_date
                }

                cur.execute(
                    """
                    INSERT INTO BOOKINGS
                        (EMAIL, NAME, CHECKIN, CHECKOUT)
                    VALUES
                        (:email, :name, :in, :out);
                    """,
                    args
                )

                booking_id = cur.lastrowid

                booked_rooms: list[dict[str, Any]] = list(map(
                    lambda room: {
                        "room_id": room[0],
                        "book_id": booking_id,
                    },
                    rooms
                ))

                cur.executemany(
                    """
                    INSERT INTO BOOKED_ROOMS
                        (ROOM_ID, BOOKING_ID)
                    VALUES
                        (:room_id, :book_id);
                    """,
                    booked_rooms
                )
                
                con.commit()

                price = 0

                for room in rooms:
                    price += room[1]

                return {
                    "data": {
                        "status": "SUCCESS",
                        "total": price
                    }
                }

            else:
                return {
                    "data": {
                        "status": "FAILED",
                        "total": 0
                    }
                }
        
        except:
            return {
                "data": {},
                "status": "ERROR - Execution failed."
            }