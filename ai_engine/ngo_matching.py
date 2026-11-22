
import math


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the distance between two geographical coordinates
    using the Haversine formula. Returns distance in kilometres.
    """

    if None in (lat1, lon1, lat2, lon2):
        return None

    earth_radius_km = 6371

    lat1 = math.radians(float(lat1))
    lon1 = math.radians(float(lon1))
    lat2 = math.radians(float(lat2))
    lon2 = math.radians(float(lon2))

    latitude_difference = lat2 - lat1
    longitude_difference = lon2 - lon1

    a = (
        math.sin(latitude_difference / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(longitude_difference / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius_km * c


def match_ngos(donation, ngos):
    """
    Rank NGOs according to their suitability for a food donation.

    Matching factors:
    - Food category compatibility
    - NGO storage capacity
    - Geographical distance
    - Donation urgency

    Returns a ranked list of NGO recommendations.
    """

    recommendations = []

    donation_category = (
        getattr(donation, "food_category", "") or ""
    ).strip().lower()

    donation_quantity = float(
        getattr(donation, "quantity_kg", 0) or 0
    )

    donation_latitude = getattr(donation, "latitude", None)
    donation_longitude = getattr(donation, "longitude", None)

    urgency_score = float(
        getattr(donation, "urgency_score", 0) or 0
    )

    for ngo in ngos:

        if not getattr(ngo, "is_active", True):
            continue

        score = 0
        reasons = []

        # -----------------------------------------
        # 1. FOOD CATEGORY COMPATIBILITY
        # -----------------------------------------

        preferred_categories = (
            getattr(ngo, "preferred_categories", "") or ""
        )

        preferred_categories = [
            category.strip().lower()
            for category in preferred_categories.split(",")
            if category.strip()
        ]

        if preferred_categories:
            if donation_category not in preferred_categories:
                continue

        score += 30
        reasons.append("Food category compatible")

        # -----------------------------------------
        # 2. NGO STORAGE CAPACITY
        # -----------------------------------------

        capacity = getattr(ngo, "capacity_kg", None)

        if capacity is not None:
            capacity = float(capacity)

            if capacity < donation_quantity:
                continue

        score += 30
        reasons.append("Sufficient storage capacity")

        # -----------------------------------------
        # 3. GEOGRAPHICAL DISTANCE
        # -----------------------------------------

        distance = calculate_distance(
            donation_latitude,
            donation_longitude,
            getattr(ngo, "latitude", None),
            getattr(ngo, "longitude", None)
        )

        if distance is not None:

            if distance <= 5:
                score += 25
                reasons.append("Very close to donation")

            elif distance <= 15:
                score += 20
                reasons.append("Within nearby service area")

            elif distance <= 30:
                score += 10
                reasons.append("Within reasonable distance")

            else:
                score += 5
                reasons.append("Farther from donation location")

        else:
            reasons.append("Distance unavailable")

        # -----------------------------------------
        # 4. DONATION URGENCY
        # -----------------------------------------

        if urgency_score >= 80:
            score += 15
            reasons.append("High-priority urgent donation")

        elif urgency_score >= 60:
            score += 12
            reasons.append("Urgent donation")

        elif urgency_score >= 35:
            score += 8
            reasons.append("Moderate donation urgency")

        else:
            score += 5
            reasons.append("Normal donation urgency")

        recommendations.append({
            "ngo": ngo,
            "score": round(score, 2),
            "distance_km": (
                round(distance, 2)
                if distance is not None
                else None
            ),
            "reasons": reasons
        })

    recommendations.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return recommendations
