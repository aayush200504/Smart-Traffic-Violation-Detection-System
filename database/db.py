import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'traffic.db')

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS vehicle_owners (
            plate_number TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT,
            vehicle_type TEXT DEFAULT 'Car',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS violation_types (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            amount INTEGER NOT NULL,
            severity TEXT DEFAULT 'Medium',
            section TEXT
        );
        CREATE TABLE IF NOT EXISTS violations (
            id TEXT PRIMARY KEY,
            plate_number TEXT,
            violation_type TEXT,
            violation_name TEXT,
            amount INTEGER,
            image_path TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            paid_at TEXT,
            notes TEXT
        );
    ''')
    
    violations = [
        ('red_light','Red Light Jumping','Vehicle crossed signal during red phase',1500,'High','MV Act Sec 119'),
        ('helmet','Helmetless Riding','Two-wheeler rider without helmet',500,'Medium','MV Act Sec 129'),
        ('wrong_lane','Wrong Lane Driving','Vehicle driving in incorrect lane',1000,'Medium','MV Act Sec 112'),
        ('speeding','Over Speeding','Vehicle exceeding speed limit',2000,'High','MV Act Sec 183'),
        ('no_seatbelt','No Seat Belt','Driver/passenger without seat belt',1000,'Medium','MV Act Sec 194B'),
        ('mobile_use','Mobile Phone Use','Using mobile phone while driving',5000,'High','MV Act Sec 184'),
        ('triple_riding','Triple Riding','Three or more persons on two-wheeler',1000,'Medium','MV Act Sec 128'),
        ('no_parking','No Parking Violation','Vehicle parked in no-parking zone',500,'Low','MV Act Sec 122'),
        ('hit_run','Hit and Run','Vehicle involved in accident and fled scene',25000,'Critical','MV Act Sec 161'),
        ('drunk_driving','Drunk Driving','Driving under influence of alcohol',10000,'Critical','MV Act Sec 185'),
    ]
    db.executemany('INSERT OR IGNORE INTO violation_types VALUES (?,?,?,?,?,?)', violations)
    
    owners = [
        ('MH12MN6565','Rahul Sharma','rahul.sharma@gmail.com','+919876543210','45, Koregaon Park, Pune, MH','Car'),
        ('MH14AB1234','Priya Patel','priya.patel@yahoo.com','+919823456789','12, Baner Road, Pune, MH','Bike'),
        ('MH20CD5678','Amit Kumar','amit.kumar@hotmail.com','+919812345678','78, FC Road, Pune, MH','Car'),
        ('MH12XY9090','Sneha Desai','sneha.desai@gmail.com','+919765432109','33, Viman Nagar, Pune, MH','Scooty'),
        ('DL01AB4321','Vikram Singh','vikram.singh@gmail.com','+919711234567','15, Connaught Place, New Delhi','Car'),
        ('KA03MN7654','Anjali Rao','anjali.rao@gmail.com','+918976543210','22, Indiranagar, Bengaluru, KA','Bike'),
        ('GJ05CD2345','Ravi Mehta','ravi.mehta@gmail.com','+919898765432','8, SG Highway, Ahmedabad, GJ','Car'),
        ('TN09EF8765','Kavitha Nair','kavitha.nair@gmail.com','+919444321098','55, Anna Nagar, Chennai, TN','Car'),
    ]
    db.executemany('INSERT OR IGNORE INTO vehicle_owners (plate_number,name,email,phone,address,vehicle_type) VALUES (?,?,?,?,?,?)', owners)
    db.commit()
    db.close()