from backend.app.database import engine
from sqlalchemy import text, inspect

inspector = inspect(engine)
cols = [c['name'] for c in inspector.get_columns('attendance')]
print('Existing columns:', cols)

with engine.connect() as conn:
    if 'attendance_type' not in cols:
        conn.execute(text("ALTER TABLE attendance ADD COLUMN attendance_type TEXT NOT NULL DEFAULT 'daily'"))
        print('Added attendance_type')
    else:
        print('attendance_type already exists')

    if 'subject_id' not in cols:
        conn.execute(text("ALTER TABLE attendance ADD COLUMN subject_id INTEGER REFERENCES subjects(id)"))
        print('Added subject_id')
    else:
        print('subject_id already exists')

    if 'period_label' not in cols:
        conn.execute(text("ALTER TABLE attendance ADD COLUMN period_label TEXT"))
        print('Added period_label')
    else:
        print('period_label already exists')

    if 'logged_by_id' not in cols:
        conn.execute(text("ALTER TABLE attendance ADD COLUMN logged_by_id INTEGER REFERENCES users(id)"))
        print('Added logged_by_id')
    else:
        print('logged_by_id already exists')

    conn.commit()
    print('Migration complete')
