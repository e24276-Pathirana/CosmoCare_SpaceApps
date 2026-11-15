import sqlite3

def seed_astronauts():

    conn = sqlite3.connect('cosmo_care.db')
    cursor = conn.cursor()


    astronauts_data = [
        ("A004", "Dr. Sarah Mitchell", 42, "Female", 170.5, 65.0, "High", 180),
        ("A005", "Cmdr. James Holden", 48, "Male", 182.0, 84.5, "Moderate", 365),
        ("A006", "Dr. Elena Rostova", 37, "Female", 165.0, 58.0, "High", 500),
        ("A007", "Marcus Chen", 39, "Male", 175.0, 76.0, "High", 90)
    ]



    cursor.executemany('''
        INSERT OR IGNORE INTO astronauts 
        (astronaut_id, name, age, sex, height_cm, weight_kg, fitness_level, mission_duration_days)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', astronauts_data)

    conn.commit()
    conn.close()
    print("done!")

if __name__ == "__main__":
    seed_astronauts()