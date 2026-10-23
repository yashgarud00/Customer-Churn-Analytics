# Run Instructions (Windows)

These steps are for running the project from the ZIP downloaded from GitHub. For a basic presentation, you only need to run the web dashboard.

## 1. Download and extract the ZIP

1. Open the project repository on GitHub and select **Code → Download ZIP**.
2. In File Explorer, right-click the downloaded ZIP and select **Extract All**.
3. Open the extracted `Customer-Churn-Analytics` folder.

## 2. Run the dashboard

The dashboard loads its bundled data from `dashboard_data.json`. Because browsers may block that request when the HTML file is opened directly, serve the project folder over localhost:

1. Install Python 3 if it is not already installed. Python is used here only to serve the dashboard; no project packages are required.
2. Open PowerShell in the extracted `Customer-Churn-Analytics` folder. In File Explorer, you can open the folder, click the address bar, type `powershell`, and press Enter.
3. Start a local web server:

   ```powershell
   py -m http.server 8000
   ```

4. Leave that PowerShell window open. In a browser, visit:

   [http://localhost:8000/dashboard/](http://localhost:8000/dashboard/)

5. To stop the server after the demo, return to PowerShell and press **Ctrl+C**.

If `py` is not recognized, install Python from [python.org](https://www.python.org/downloads/windows/) and enable **Add Python to PATH** during installation. Alternatively, open the project in Visual Studio Code and use a local web-server extension to serve the project folder.

## 3. Optional: run the prediction API

The dashboard demo does not require the API. To run the separate Flask API, install Python 3.11 and open PowerShell in the project folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Keep the PowerShell window open, then visit [http://127.0.0.1:5000/health](http://127.0.0.1:5000/health) to check the API. To stop it, press **Ctrl+C**.

## Troubleshooting

- **Dashboard is blank or has no charts:** Confirm the local server is running and open `http://localhost:8000/dashboard/` rather than opening `index.html` directly.
- **Port 8000 is already in use:** Start the server on another port, such as `py -m http.server 8001`, then visit `http://localhost:8001/dashboard/`.
- **Charts do not load:** Check that the browser has internet access; the dashboard loads Chart.js from a CDN.
- **API reports a missing model:** Confirm the ZIP includes the `models` folder and its model files.
