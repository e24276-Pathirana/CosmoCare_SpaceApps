import sqlite3

def init_db():

    conn = sqlite3.connect('cosmo_care.db')
    cursor = conn.cursor()


    with open('schema.sql', 'r') as sql_file:
        sql_script = sql_file.read()

    cursor.executescript(sql_script)
    conn.commit()
    conn.close()
    print("Done !")

if __name__ == "__main__":
    init_db()