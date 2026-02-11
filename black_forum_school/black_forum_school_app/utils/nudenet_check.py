# black_forum_school_app/utils/nudenet_check.py

try:
    from nudenet import NudeDetector
    detector = NudeDetector()
    print("NudeNet (forum): OK")
except Exception as e:
    detector = None
    print("NudeNet (forum): OFF", e)

NSFW_THRESHOLD = 0.25

BAD_CLASSES = {
    "FEMALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "BUTTOCKS_EXPOSED",
    "ANUS_EXPOSED",
    "FEMALE_GENITALIA_COVERED",
    "BUTTOCKS_COVERED",
}


def check_image_safe(image_path: str):
    """
    True  -> изображение безопасно
    False -> 18+
    None  -> не удалось проверить
    """
    if detector is None:
        return None

    try:
        detections = detector.detect(image_path)
        for d in detections:
            cls = d.get("class")
            score = float(d.get("score", 0))
            if cls in BAD_CLASSES and score >= NSFW_THRESHOLD:
                return False
        return True
    except Exception as e:
        print("Forum NSFW error:", e)
        return None




def check_image_safe(image_path):
    try:
        from nudenet import NudeClassifier
        classifier = NudeClassifier()
        result = classifier.classify(image_path)

        for _, scores in result.items():
            if scores.get("porn", 0) > 0.6:
                return False

        return True
    except Exception:
        # если не удалось проверить — БЛОК
        return None
