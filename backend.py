#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OLKA Sprint Dashboard Backend
Jira'dan canlı sprint verisini çeker ve API üzerinden sunar.
"""

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
import os
from datetime import datetime
from typing import Dict, List

app = FastAPI()

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sabit ayarlar (OLKA ortamı)
CLOUD_ID = "501735f2-facf-4778-8cd4-8e1c19904057"
PROJECT = "EWT"
BOARD_ID = "1"

# Veri depolama
cached_data = {
    "issues": [],
    "sprint": {},
    "stats": {},
    "last_update": None,
    "active_connections": set()
}

# Status kategorileri
STATUS_CATEGORIES = {
    "BASLAMADI": ["Plan", "To Do"],
    "DEVAM": ["Development", "Review", "UAT", "In Progress"],
    "RISK": ["Block", "Blocked", "Rejected"],
    "TAMAM": ["Ready for Ship", "Done", "ONLIVE", "Completed"]
}

# Marka eşlemesi
BRAND_MAPPING = {
    "Skechers": "Skechers",
    "iOS": "Mobile",
    "Android": "Mobile",
    "Klaud": "Klaud",
    "High5": "High5",
    "Brooks": "Brooks",
    "Hunter": "Hunter",
    "Steve Madden": "Steve Madden",
}

def load_sample_data():
    """Örnek sprint verisini yükle (geliştirme için)"""
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def categorize_status(status: str) -> str:
    """Status'u faza dönüştür"""
    for category, statuses in STATUS_CATEGORIES.items():
        if status in statuses:
            return category
    return "BILINMEYEN"

def get_brand(issue_type: str, labels: List[str] = None) -> str:
    """Issue type'dan marka belirle"""
    labels = labels or []
    return BRAND_MAPPING.get(issue_type, "Diğer")

def process_issues(raw_issues: List[Dict]) -> Dict:
    """Raw issue'ları işle ve istatistikler oluştur"""
    processed = []
    brands = {}
    phases = {}
    
    for issue in raw_issues:
        # Skip Task ve Tasarım
        if issue.get("type") in ["Task", "Tasarım"]:
            continue
        
        brand = get_brand(issue.get("type", ""), issue.get("labels", []))
        phase = categorize_status(issue.get("status", ""))
        
        # Devreden tespiti
        is_carried = issue.get("sprint_count", 0) > 1
        
        processed.append({
            "key": issue.get("key"),
            "summary": issue.get("summary"),
            "status": issue.get("status"),
            "phase": phase,
            "type": issue.get("type"),
            "priority": issue.get("priority", "—"),
            "assignee": issue.get("assignee", "Atanmamış"),
            "duedate": issue.get("duedate"),
            "brand": brand,
            "labels": issue.get("labels", []),
            "is_carried": is_carried,
            "sprint_count": issue.get("sprint_count", 1)
        })
        
        # İstatistikler
        if brand not in brands:
            brands[brand] = {"total": 0, "by_phase": {}}
        brands[brand]["total"] += 1
        if phase not in brands[brand]["by_phase"]:
            brands[brand]["by_phase"][phase] = 0
        brands[brand]["by_phase"][phase] += 1
        
        if phase not in phases:
            phases[phase] = 0
        phases[phase] += 1
    
    return {
        "issues": processed,
        "brands": brands,
        "phases": phases,
        "total": len(processed)
    }

@app.get("/api/sprint")
async def get_sprint_data():
    """Aktif sprint verisini döndür"""
    if not cached_data["issues"]:
        # İlk yüklemede örnek veriyi yükle
        raw_issues = load_sample_data()
        processed = process_issues(raw_issues)
        
        cached_data["issues"] = processed["issues"]
        cached_data["stats"] = {
            "brands": processed["brands"],
            "phases": processed["phases"],
            "total": processed["total"]
        }
        cached_data["sprint"] = {
            "name": "SPRINT 16062026",
            "date_range": "16 Haziran - 23 Haziran 2026"
        }
        cached_data["last_update"] = datetime.now().isoformat()
    
    return {
        "sprint": cached_data["sprint"],
        "issues": cached_data["issues"],
        "stats": cached_data["stats"],
        "last_update": cached_data["last_update"],
        "connection_count": len(cached_data["active_connections"])
    }

@app.get("/api/stats")
async def get_stats():
    """İstatistikleri döndür"""
    if not cached_data["stats"]:
        await get_sprint_data()
    
    return cached_data["stats"]

@app.get("/api/brands")
async def get_brands():
    """Markalar ve dağılımları döndür"""
    if not cached_data["stats"]:
        await get_sprint_data()
    
    return cached_data["stats"].get("brands", {})

@app.get("/api/issues/by-brand/{brand}")
async def get_issues_by_brand(brand: str):
    """Markaya göre issue'ları filtrele"""
    issues = [i for i in cached_data["issues"] if i["brand"] == brand]
    return {
        "brand": brand,
        "issues": issues,
        "total": len(issues),
        "by_phase": {}
    }

@app.get("/api/issues/by-phase/{phase}")
async def get_issues_by_phase(phase: str):
    """Faza göre issue'ları filtrele"""
    issues = [i for i in cached_data["issues"] if i["phase"] == phase]
    return {
        "phase": phase,
        "issues": issues,
        "total": len(issues)
    }

@app.get("/api/refresh")
async def refresh_data():
    """Manuel veri yenileme (Jira'dan çekme - geliştirme aşamasında)"""
    # TODO: Gerçek Jira API entegrasyonu
    return {"status": "refresh", "message": "Jira bağlantısı yapılandırılıyor..."}

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Dashboard HTML'ini serve et"""
    html = """
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>OLKA Sprint Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/react@18/umd/react.production.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/react-dom@18/umd/react-dom.production.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/@babel/standalone/babel.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/recharts@2.10.0/dist/Recharts.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container { max-width: 1400px; margin: 0 auto; }
            .header {
                background: white;
                border-radius: 12px;
                padding: 24px;
                margin-bottom: 24px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            .header h1 {
                color: #333;
                font-size: 28px;
                margin-bottom: 8px;
            }
            .header p {
                color: #666;
                font-size: 14px;
            }
            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 24px;
            }
            .card {
                background: white;
                border-radius: 12px;
                padding: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                transition: transform 0.2s;
            }
            .card:hover { transform: translateY(-4px); }
            .stat-card {
                text-align: center;
            }
            .stat-number {
                font-size: 36px;
                font-weight: bold;
                color: #667eea;
                margin: 12px 0;
            }
            .stat-label {
                color: #666;
                font-size: 14px;
            }
            .brand-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
                gap: 16px;
                margin-top: 16px;
            }
            .brand-item {
                background: #f8f9fa;
                padding: 12px;
                border-radius: 8px;
                border-left: 4px solid #667eea;
                cursor: pointer;
            }
            .brand-item:hover {
                background: #e9ecef;
            }
            .brand-name {
                font-weight: 600;
                color: #333;
                font-size: 14px;
            }
            .brand-count {
                color: #667eea;
                font-size: 20px;
                font-weight: bold;
                margin-top: 8px;
            }
            .issues-table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 16px;
            }
            .issues-table th {
                background: #f8f9fa;
                padding: 12px;
                text-align: left;
                font-weight: 600;
                border-bottom: 2px solid #e9ecef;
                font-size: 13px;
                color: #666;
            }
            .issues-table td {
                padding: 12px;
                border-bottom: 1px solid #e9ecef;
                font-size: 13px;
            }
            .issue-key {
                font-weight: 600;
                color: #667eea;
                font-family: 'Courier New', monospace;
            }
            .phase-badge {
                display: inline-block;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
            }
            .phase-BASLAMADI { background: #e3f2fd; color: #1976d2; }
            .phase-DEVAM { background: #f3e5f5; color: #7b1fa2; }
            .phase-RISK { background: #ffebee; color: #c62828; }
            .phase-TAMAM { background: #e8f5e9; color: #2e7d32; }
            .priority-highest { color: #d32f2f; font-weight: 600; }
            .priority-high { color: #f57c00; font-weight: 600; }
            .priority-medium { color: #fbc02d; font-weight: 600; }
            .priority-low { color: #388e3c; font-weight: 600; }
            .refresh-btn {
                background: #667eea;
                color: white;
                border: none;
                padding: 10px 16px;
                border-radius: 6px;
                cursor: pointer;
                font-weight: 600;
                transition: background 0.2s;
            }
            .refresh-btn:hover { background: #5568d3; }
            .last-update {
                font-size: 12px;
                color: #999;
                margin-top: 12px;
            }
            .tabs {
                display: flex;
                gap: 8px;
                margin-bottom: 16px;
                border-bottom: 2px solid #e9ecef;
            }
            .tab {
                padding: 12px 16px;
                border: none;
                background: none;
                cursor: pointer;
                color: #666;
                font-weight: 500;
                border-bottom: 3px solid transparent;
                transition: all 0.2s;
            }
            .tab.active {
                color: #667eea;
                border-bottom-color: #667eea;
            }
            .tab:hover {
                color: #667eea;
            }
        </style>
    </head>
    <body>
        <div id="root"></div>
        <script type="text/babel">
            const { useState, useEffect } = React;
            
            function Dashboard() {
                const [data, setData] = useState(null);
                const [activeTab, setActiveTab] = useState('overview');
                const [selectedBrand, setSelectedBrand] = useState(null);
                const [loading, setLoading] = useState(true);
                
                useEffect(() => {
                    fetchData();
                    const interval = setInterval(fetchData, 30000); // 30 saniyede bir güncelle
                    return () => clearInterval(interval);
                }, []);
                
                const fetchData = async () => {
                    try {
                        const response = await fetch('/api/sprint');
                        const result = await response.json();
                        setData(result);
                        setLoading(false);
                    } catch (error) {
                        console.error('Veri yüklenirken hata:', error);
                        setLoading(false);
                    }
                };
                
                if (loading) {
                    return <div style={{color: 'white', textAlign: 'center', marginTop: '100px'}}>Yükleniyor...</div>;
                }
                
                if (!data) {
                    return <div style={{color: 'white', textAlign: 'center', marginTop: '100px'}}>Veri yüklenemedi</div>;
                }
                
                const getPhaseBadge = (phase) => {
                    return <span className={`phase-badge phase-${phase}`}>{phase}</span>;
                };
                
                const getPriorityClass = (priority) => {
                    const p = priority.toLowerCase();
                    if (p.includes('highest')) return 'priority-highest';
                    if (p.includes('high')) return 'priority-high';
                    if (p.includes('medium')) return 'priority-medium';
                    return 'priority-low';
                };
                
                return (
                    <div className="container">
                        <div className="header">
                            <h1>🎯 OLKA Sprint Dashboard</h1>
                            <p>{data.sprint.name} • {data.sprint.date_range}</p>
                            <div className="last-update">
                                ⏱️ Son güncelleme: {new Date(data.last_update).toLocaleTimeString('tr-TR')}
                            </div>
                            <button className="refresh-btn" onClick={fetchData} style={{marginTop: '12px'}}>
                                🔄 Şimdi Güncelle
                            </button>
                        </div>
                        
                        <div className="card">
                            <div className="tabs">
                                <button 
                                    className={`tab ${activeTab === 'overview' ? 'active' : ''}`}
                                    onClick={() => setActiveTab('overview')}
                                >
                                    📊 Genel Görünüm
                                </button>
                                <button 
                                    className={`tab ${activeTab === 'issues' ? 'active' : ''}`}
                                    onClick={() => setActiveTab('issues')}
                                >
                                    📝 Tüm İşler
                                </button>
                                <button 
                                    className={`tab ${activeTab === 'brands' ? 'active' : ''}`}
                                    onClick={() => setActiveTab('brands')}
                                >
                                    🏷️ Markalar
                                </button>
                            </div>
                            
                            {activeTab === 'overview' && (
                                <div>
                                    <div className="grid">
                                        <div className="card stat-card">
                                            <div className="stat-label">Toplam İşler</div>
                                            <div className="stat-number">{data.stats.total}</div>
                                        </div>
                                        <div className="card stat-card">
                                            <div className="stat-label">Tamamlanan</div>
                                            <div className="stat-number" style={{color: '#4caf50'}}>
                                                {data.stats.phases.TAMAM || 0}
                                            </div>
                                        </div>
                                        <div className="card stat-card">
                                            <div className="stat-label">Devam Eden</div>
                                            <div className="stat-number" style={{color: '#2196f3'}}>
                                                {data.stats.phases.DEVAM || 0}
                                            </div>
                                        </div>
                                        <div className="card stat-card">
                                            <div className="stat-label">Risk</div>
                                            <div className="stat-number" style={{color: '#f44336'}}>
                                                {data.stats.phases.RISK || 0}
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <div className="card">
                                        <h3>Marka Dağılımı</h3>
                                        <div className="brand-grid">
                                            {Object.entries(data.stats.brands).map(([brand, stats]) => (
                                                <div key={brand} className="brand-item">
                                                    <div className="brand-name">{brand}</div>
                                                    <div className="brand-count">{stats.total}</div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            )}
                            
                            {activeTab === 'issues' && (
                                <table className="issues-table">
                                    <thead>
                                        <tr>
                                            <th>Anahtar</th>
                                            <th>Özet</th>
                                            <th>Marka</th>
                                            <th>Faz</th>
                                            <th>Öncelik</th>
                                            <th>Atanan Kişi</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {data.issues.map((issue) => (
                                            <tr key={issue.key}>
                                                <td><span className="issue-key">{issue.key}</span></td>
                                                <td>{issue.summary}</td>
                                                <td><strong>{issue.brand}</strong></td>
                                                <td>{getPhaseBadge(issue.phase)}</td>
                                                <td><span className={getPriorityClass(issue.priority)}>{issue.priority}</span></td>
                                                <td>{issue.assignee}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                            
                            {activeTab === 'brands' && (
                                <div>
                                    {Object.entries(data.stats.brands).map(([brand, stats]) => (
                                        <div key={brand} className="card" style={{marginBottom: '16px'}}>
                                            <h3>{brand} ({stats.total})</h3>
                                            <div style={{marginTop: '12px', fontSize: '13px'}}>
                                                {Object.entries(stats.by_phase).map(([phase, count]) => (
                                                    <div key={phase} style={{marginBottom: '8px'}}>
                                                        <span>{getPhaseBadge(phase)}</span>
                                                        <span style={{marginLeft: '8px', fontWeight: 600}}>{count}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                );
            }
            
            ReactDOM.createRoot(document.getElementById('root')).render(<Dashboard />);
        </script>
    </body>
    </html>
    """
    return html

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
