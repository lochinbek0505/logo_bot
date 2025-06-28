def check_audio(text1: str, text2: str):
    first = text1.lower().replace("'", "").split(" ")
    second = text2.lower().replace("'", "").split(" ")

    for i in range(3):
        if not (first[i] in second):
            return False
    return True
