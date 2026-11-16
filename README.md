# Gayatri Jewellers – Rate Board (Step 3: database + admin panel)

    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    python create_admin.py        (once: choose your admin username and password)
    python app.py

- TV board:  http://<PC-address>:5000/      (double-click for full screen)
- Admin:     http://<PC-address>:5000/admin

Pricing (admin panel): 22K and 20K are calculated as 24K rate × purity % (default 91.6 and 83.3, editable);
every category can have a ₹ margin added; TV rates can be rounded to ₹1/5/10/50/100.

Modes: Demo (sample data, labelled on the TV) or Manual (rates you type). Live mode is not built yet.
Switching mode clears stored rates so demo numbers can never be shown as real ones.
Set HOST=127.0.0.1 if the TV browser is on the same PC; keep 0.0.0.0 for a TV box on your Wi-Fi.
