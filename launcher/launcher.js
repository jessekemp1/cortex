let countdown = 10;
let data = null;

async function loadData() {
    const response = await fetch('launcher_data.json?' + Date.now());
    data = await response.json();
    renderStats();
    renderProjects();
    countdown = 10;
}

function renderStats() {
    const running = data.projects.filter(p => p.status === 'running' || (p.services && p.services.some(s => s.status === 'running'))).length;
    const conflicts = detectConflicts();
    document.getElementById('stats').innerHTML = '<div class="stat-card"><div class="stat-value">'+data.projects.length+'</div><div class="stat-label">Total Projects</div></div><div class="stat-card"><div class="stat-value">'+running+'</div><div class="stat-label">Running</div></div><div class="stat-card"><div class="stat-value">'+Object.keys(data.running_processes).length+'</div><div class="stat-label">Ports in Use</div></div><div class="stat-card"><div class="stat-value" style="color:'+(conflicts>0?'#ef4444':'#10b981')+'">'+conflicts+'</div><div class="stat-label">Port Conflicts</div></div>';
}

function detectConflicts() {
    const portMap = {};
    let conflicts = 0;
    data.projects.forEach(project => {
        if (project.port) { if (!portMap[project.port]) portMap[project.port] = []; portMap[project.port].push(project.name); }
        if (project.services) { project.services.forEach(service => { if (!portMap[service.port]) portMap[service.port] = []; portMap[service.port].push(project.name+" ("+service.name+")"); }); }
    });
    Object.values(portMap).forEach(projects => { if (projects.length > 1) conflicts += projects.length - 1; });
    return conflicts;
}

function hasConflict(project) { if (!project.port) return false; return data.projects.filter(p => p.port === project.port).length > 1; }

function renderProjects() {
    const html = data.projects.map(project => { const conflict = hasConflict(project); return '<div class="project-card"><div class="project-header"><div class="project-name">'+project.name+'</div><span class="status-badge status-'+(conflict?'conflict':project.status)+'">'+(conflict?'⚠️ CONFLICT':project.status)+'</span></div><div class="project-info"><div class="info-row"><span class="info-label">Type</span><span class="info-value">'+project.type+'</span></div>'+(project.port?'<div class="info-row"><span class="info-label">Port</span><span class="info-value'+(conflict?' port-conflict':'')+'" >'+project.port+'</span></div>':'')+(project.pid?'<div class="info-row"><span class="info-label">PID</span><span class="info-value">'+project.pid+'</span></div>':'')+'</div><div class="actions">'+(project.status==='running'?'<button class="btn btn-open" onclick="openURL('+project.port+')">Open</button><button class="btn btn-stop" onclick="showCommand(\'kill '+project.pid+'\')">Stop</button>':'<button class="btn btn-start"'+(conflict?' disabled':'')+' onclick="showCommand(\'cd '+project.path+' && '+project.start_command+'\')">'+(conflict?'Resolve Conflict':'Start')+'</button>')+'</div></div>'; }).join('');
    document.getElementById('projects').innerHTML = html;
}

function openURL(port) { window.open('http://localhost:'+port, '_blank'); }
function showCommand(command) { alert('Run in terminal:\\n\\n'+command); }

setInterval(() => { countdown--; document.getElementById('countdown').textContent = countdown+'s'; if (countdown <= 0) loadData(); }, 1000);
loadData();
