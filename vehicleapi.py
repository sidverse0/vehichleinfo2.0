from flask import Flask, request, Response
import requests
import re
import json

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

API_URL = "https://www.smcinsurance.com/central/centralcall/CallReqWithHeader"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36",
    "Content-Type": "application/json",
    "sec-ch-ua-platform": '"Android"',
    "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
    "dnt": "1",
    "sec-ch-ua-mobile": "?1",
    "origin": "https://www.smcinsurance.com",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "referer": "https://www.smcinsurance.com/",
    "accept-language": "en-GB,en;q=0.9,hi;q=0.8",
    "priority": "u=1, i",
    "Cookie": "_gcl_au=1.1.497317222.1777187703; _ga=GA1.2.161824049.1777187703; _gid=GA1.2.274183122.1777187703"
}


def pretty(data, status=200):
    """Return indented JSON response."""
    return Response(
        json.dumps(data, indent=4, ensure_ascii=False),
        status=status,
        mimetype="application/json"
    )


def validate_vehicle_number(vnum: str) -> bool:
    return bool(re.match(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$", vnum))


def get_vehicle_no_from_request():
    """Support /api/vehicle?=UP80FZ7810 and named params."""
    for key, val in request.args.items():
        if key.strip() == "":
            return val.strip()
    named = request.args.get("vehicle_no") or request.args.get("vno") or request.args.get("v")
    if named:
        return named.strip()
    qs = request.query_string.decode("utf-8").strip()
    if qs:
        if qs.startswith("="):
            return qs[1:].strip()
        if "=" not in qs:
            return qs.strip()
    return ""


def flatten_response(response_obj):
    """
    Dynamic flatten:
    - Top-level keys ko as-is rakhta hai.
    - Nested dict (jaise rtoData) ke saare keys top pe merge karta hai.
    - Collision ho toh '<parent>_<child>' bana ke rakhta hai.
    - Future me koi naya nested field aaye toh bhi auto include ho jayega.
    """
    flat = {}

    for key, value in response_obj.items():
        if isinstance(value, dict):
            for sub_key, sub_val in value.items():
                if sub_key in flat:
                    flat[f"{key}_{sub_key}"] = sub_val
                else:
                    flat[sub_key] = sub_val
        else:
            flat[key] = value

    return flat


@app.route("/", methods=["GET"])
def home():
    return pretty({
        "success": True,
        "message": "Vehicle Details API",
        "usage": "/api/vehicle?=UP80FZ7810"
    })


@app.route("/api/vehicle", methods=["GET"])
def get_vehicle_details():
    raw = get_vehicle_no_from_request()
    vehicle_no = raw.upper().replace(" ", "").replace("-", "")

    if not vehicle_no:
        return pretty({
            "success": False,
            "error": "Vehicle number required",
            "example": "/api/vehicle?=UP80FZ7810"
        }, 400)

    if not validate_vehicle_number(vehicle_no):
        return pretty({
            "success": False,
            "error": "Invalid vehicle number format",
            "example": "UP80FZ7810",
            "got": raw
        }, 400)

    try:
        payload = {
            "URL": "GetVaahanDetailsByVehicleNo",
            "Props": [vehicle_no],
            "Token": ""
        }

        resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
        api_json = resp.json()

        if api_json.get("statusCode") != 200 or not api_json.get("response"):
            return pretty({
                "success": False,
                "error": api_json.get("message", "Vehicle not found")
            }, 404)

        response_obj = api_json["response"]

        # Dynamic flatten — ek bhi field miss nahi hoga, future-proof
        flat = flatten_response(response_obj)

        result = {"success": True}
        result.update(flat)

        return pretty(result, 200)

    except requests.exceptions.Timeout:
        return pretty({"success": False, "error": "Upstream timeout"}, 504)
    except requests.exceptions.RequestException as e:
        return pretty({"success": False, "error": f"Request failed: {str(e)}"}, 502)
    except Exception as e:
        return pretty({"success": False, "error": f"Server error: {str(e)}"}, 500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)