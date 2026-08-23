# How to Connect Free Persistent PostgreSQL Database on Render (60 Seconds)

To make your online cloud deployment permanently store all registered schools, students, and financial records through future GitHub code pushes:

---

### Step 1: Create a Free PostgreSQL Database on Render
1. Log in to your **[Render Dashboard](https://dashboard.render.com/)**.
2. Click the **`New +`** button in the top right corner and select **`PostgreSQL`**.
3. Fill in the basic details:
   * **Name:** `edumanage360-db`
   * **Database:** `edumanage360`
   * **User:** `edumanage360_user`
   * **Region:** Same region as your web service (e.g. Frankfurt / Oregon)
   * **Plan:** **Free**
4. Click **`Create Database`**.

---

### Step 2: Copy the Internal Database URL
1. Once the database status turns **Available** (takes ~30 seconds), scroll down to the **Connections** section.
2. Click **Copy** next to the **`Internal Database URL`** (starts with `postgres://...` or `postgresql://...`).

---

### Step 3: Add `DATABASE_URL` to Your Web Service
1. Open your **`sms-nald`** Web Service in the Render Dashboard.
2. Go to the **`Environment`** tab in the left sidebar.
3. Click **`Add Environment Variable`**:
   * **Key:** `DATABASE_URL`
   * **Value:** Paste the Internal Database URL you copied in Step 2.
4. Click **`Save Changes`**.

---

### 🚀 Verification
Render will automatically redeploy the web service with PostgreSQL enabled.
You can verify the connection anytime by visiting:
👉 **`https://sms-nald.onrender.com/api/health`**

It will show:
```json
{
  "status": "healthy",
  "environment": "cloud_production",
  "database": {
    "engine": "PostgreSQL",
    "status": "connected"
  }
}
```
All schools, students, teachers, and data will now be **100% permanent forever** through all future updates!
