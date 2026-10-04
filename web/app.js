let cfg = {};
let packs = [];
let region = null;
let logs = [];
let modalKeydownHandler = null;

const $ = (id) => document.getElementById(id);

/* ============ 初始化 ============ */
window.addEventListener('pywebviewready', async () => {
    try {
        const data = await pywebview.api.get_config();
        cfg = data.config || {};
        region = data.region || null;
        packs = data.packs || [];

        fillForm(cfg);
        fillTemplatePacks(packs, cfg.template_pack_name);
        updateRegionText();

        bindEvents();
        setStatus("就绪", "idle");
    } catch (e) {
        console.error("初始化失败:", e);
        setStatus("初始化失败", "error");
    }
});

/* ============ 表单填充 ============ */
function setVal(id, v) {
    const el = $(id);
    if (el) el.value = (v === undefined || v === null) ? "" : v;
}

function fillForm(c) {
    setVal("start_delay", c.start_delay);
    setVal("target_total_time", c.target_total_time);
    setVal("fast_interval", c.fast_interval);
    setVal("slow_interval", c.slow_interval);
    setVal("big_pause_min", c.big_pause_min);
    setVal("big_pause_max", c.big_pause_max);
    setVal("cell_shrink", c.cell_shrink);
    setVal("match_score_max", c.match_score_max);
    setVal("human_jitter", c.human_jitter);
    setVal("click_jitter", c.click_jitter);

    const sortVal = c.descending ? "desc" : "asc";
    document.querySelectorAll('input[name=sort]').forEach(el => {
        el.checked = (el.value === sortVal);
    });
    const mouseVal = c.mouse_mode || "instant";
    document.querySelectorAll('input[name=mouse]').forEach(el => {
        el.checked = (el.value === mouseVal);
    });
}

function num(id, def) {
    const el = $(id);
    if (!el) return def;
    const v = parseFloat(el.value);
    return isNaN(v) ? def : v;
}

function readForm() {
    const sortEl = document.querySelector('input[name=sort]:checked');
    const mouseEl = document.querySelector('input[name=mouse]:checked');
    return {
        start_delay: num("start_delay", 3),
        target_total_time: num("target_total_time", 20),
        fast_interval: num("fast_interval", 0.18),
        slow_interval: num("slow_interval", 0.55),
        big_pause_min: num("big_pause_min", 1.5),
        big_pause_max: num("big_pause_max", 2.5),
        cell_shrink: num("cell_shrink", 0.15),
        match_score_max: num("match_score_max", 0.15),
        human_jitter: num("human_jitter", 2),
        click_jitter: num("click_jitter", 1),
        descending: sortEl ? sortEl.value === "desc" : false,
        mouse_mode: mouseEl ? mouseEl.value : "instant",
        template_pack_name: $("template_pack") ? $("template_pack").value : "",
    };
}

function fillTemplatePacks(list, saved) {
    const sel = $("template_pack");
    if (!sel) return;
    sel.innerHTML = "";
    if (!list.length) {
        sel.innerHTML = '<option value="">(未找到模板)</option>';
        return;
    }
    list.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.name;
        opt.textContent = p.name;
        sel.appendChild(opt);
    });
    if (saved) sel.value = saved;
}

function updateRegionText() {
    const el = $("region-text");
    if (!el) return;
    if (region) {
        el.classList.add("has-value");
        el.textContent = `(${region.left}, ${region.top})   宽 ${region.width} × 高 ${region.height}`;
    } else {
        el.classList.remove("has-value");
        el.innerHTML = '<span class="region-placeholder">尚未选区，请点击"重新选区"</span>';
    }
}

function setStatus(text, type = "idle") {
    const chip = $("status");
    if (!chip) return;
    const txt = chip.querySelector(".text");
    if (txt) txt.textContent = text;
    chip.classList.remove("idle", "busy", "saved", "done", "error");
    chip.classList.add(type);
}

/* ============ 事件绑定 ============ */
function bindEvents() {
    const btnSelect = $("btn-select");
    if (btnSelect) btnSelect.onclick = onSelect;

    const btnSave = $("btn-save");
    if (btnSave) btnSave.onclick = onSave;

    const btnStart = $("btn-start");
    if (btnStart) btnStart.onclick = onStart;

    const btnHelp = $("btn-help");
    if (btnHelp) btnHelp.onclick = showHelp;

    const btnExit = $("btn-exit");
    if (btnExit) btnExit.onclick = onExit;

    const btnClear = $("btn-clear-log");
    if (btnClear) btnClear.onclick = () => {
        logs = [];
        renderLogs();
    };

    const filter = $("filter");
    if (filter) filter.onchange = () => renderLogs();
}

/* ============ 事件处理 ============ */
async function onSelect() {
    setStatus("选区中...", "busy");
    try {
        const res = await pywebview.api.select_region();
        if (res && res.ok) {
            region = res.region;
            updateRegionText();
        }
    } catch (e) {
        console.error(e);
        setStatus("选区失败", "error");
        setTimeout(() => setStatus("就绪", "idle"), 1500);
        return;
    }
    setStatus("就绪", "idle");
}

async function onSave() {
    console.log(">>> 保存配置按钮被点击");
    const c = readForm();
    console.log(">>> 待保存的配置:", c);
    setStatus("保存中...", "busy");
    try {
        const res = await pywebview.api.save_config(c);
        console.log(">>> 保存结果:", res);
        if (res && res.ok) {
            setStatus("配置已保存", "saved");
            setTimeout(() => setStatus("就绪", "idle"), 1500);
        } else {
            setStatus("保存失败", "error");
            showAlert("保存失败", (res && res.error) || "未知错误");
            setTimeout(() => setStatus("就绪", "idle"), 1500);
        }
    } catch (e) {
        console.error("保存异常:", e);
        setStatus("保存失败", "error");
        showAlert("保存失败", String(e));
        setTimeout(() => setStatus("就绪", "idle"), 1500);
    }
}

async function onStart() {
    console.log(">>> 开始点击按钮被点击");
    const c = readForm();
    const btn = $("btn-start");
    if (btn) btn.disabled = true;
    setStatus("点击中...", "busy");
    try {
        const res = await pywebview.api.start_click(c);
        if (!res || !res.ok) {
            if (btn) btn.disabled = false;
            setStatus("就绪", "idle");
            if (res && res.need_code) {
                askCode();
            } else if (res && res.error) {
                showAlert("错误", res.error);
            }
        }
    } catch (e) {
        console.error(e);
        if (btn) btn.disabled = false;
        setStatus("启动失败", "error");
        showAlert("启动失败", String(e));
        setTimeout(() => setStatus("就绪", "idle"), 1500);
    }
}

function onExit() {
    console.log(">>> 退出按钮被点击");
    window.close();
}

/* ============ 日志 ============ */
window.onBackendLog = (data) => {
    logs.push(data);
    renderLogs();
};

function renderLogs() {
    const fEl = $("filter");
    const f = fEl ? fEl.value : "";
    const el = $("log");
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;

    el.innerHTML = "";
    logs.forEach(item => {
        if (f && item.cat !== f) return;
        const div = document.createElement("div");
        div.className = item.cat || "info";
        div.textContent = item.msg;
        el.appendChild(div);
    });

    if (atBottom) el.scrollTop = el.scrollHeight;
}

window.onClickFinished = () => {
    const btn = $("btn-start");
    if (btn) btn.disabled = false;
    setStatus("完成", "done");
    setTimeout(() => setStatus("就绪", "idle"), 1500);
};

/* ============ 弹窗 ============ */
function showModal({ title, bodyHtml, okText = "确定", cancelText = "取消", showCancel = true, onOk }) {
    const mask = $("modal-mask");
    const titleEl = $("modal-title");
    const bodyEl = $("modal-body");
    const footEl = $("modal-foot");
    if (!mask || !titleEl || !bodyEl || !footEl) {
        alert(title + "\n\n" + bodyHtml.replace(/<[^>]+>/g, ""));
        return;
    }

    titleEl.textContent = title;
    bodyEl.innerHTML = bodyHtml;

    footEl.innerHTML = "";
    if (showCancel) {
        const btnCancel = document.createElement("button");
        btnCancel.className = "btn btn-secondary";
        btnCancel.textContent = cancelText;
        btnCancel.onclick = closeModal;
        footEl.appendChild(btnCancel);
    }
    const btnOk = document.createElement("button");
    btnOk.className = "btn btn-primary";
    btnOk.textContent = okText;
    btnOk.onclick = async () => {
        if (onOk) {
            const r = await onOk();
            if (r === false) return;
        }
        closeModal();
    };
    footEl.appendChild(btnOk);

    mask.classList.remove("hidden");

    modalKeydownHandler = (e) => {
        if (e.key === "Escape") closeModal();
        if (e.key === "Enter") btnOk.click();
    };
    document.addEventListener("keydown", modalKeydownHandler);
}

function closeModal() {
    const mask = $("modal-mask");
    if (mask) mask.classList.add("hidden");
    if (modalKeydownHandler) {
        document.removeEventListener("keydown", modalKeydownHandler);
        modalKeydownHandler = null;
    }
}

function escapeHtml(s) {
    return String(s)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
}

function showAlert(title, msg) {
    showModal({
        title: title,
        bodyHtml: `<div class="modal-text">${escapeHtml(msg)}</div>`,
        showCancel: false,
        okText: "确定",
    });
}

/* ============ 帮助 ============ */
function showHelp() {
    const helpHtml = `
<div class="help-content">
    <h4>舒尔特方格自动点击器 v2.0</h4>

    <h5>这是什么</h5>
    <p>一款自动完成"舒尔特方格"训练的小工具。程序会识别屏幕上的数字方格，并按 1 → 2 → 3 → … 的顺序自动点击。点击节奏模拟真人，可自定义总时长和停顿。</p>

    <h5>首次使用</h5>
    <ol>
        <li>打开舒尔特方格网页/程序，让 25 个数字显示在屏幕上</li>
        <li>打开本程序，点"重新选区"</li>
        <li>屏幕变暗后，按住鼠标左键拖动，框住整个 5×5 方格</li>
        <li>松开鼠标，区域自动保存</li>
        <li>点"开始点击"</li>
        <li>3 秒内切换到舒尔特方格窗口，程序自动执行</li>
    </ol>

    <h5>参数说明</h5>
    <table class="help-table">
        <tr><td>起始等待</td><td>点"开始点击"后留给你切窗口的时间（秒）</td></tr>
        <tr><td>目标总时长</td><td>整套点击的目标耗时（秒）</td></tr>
        <tr><td>最快间隔</td><td>相邻两次点击之间的最小间隔</td></tr>
        <tr><td>最慢间隔</td><td>相邻两次点击之间的最大间隔</td></tr>
        <tr><td>大停顿最小/最大</td><td>模拟"卡住"的一次停顿，随机分布在其中一步</td></tr>
        <tr><td>格子边缘收缩</td><td>识别时向内收缩的比例，避免被格子边框干扰</td></tr>
        <tr><td>匹配阈值</td><td>数字识别的相似度阈值，越小越严格</td></tr>
    </table>

    <h5>排序方向</h5>
    <ul>
        <li><b>从小到大</b>：点击顺序 1 → 2 → 3 → … → 25</li>
        <li><b>从大到小</b>：点击顺序 25 → 24 → … → 1</li>
    </ul>

    <h5>鼠标模式</h5>
    <ul>
        <li><b>瞬移</b>：鼠标直接跳到目标位置（默认，最快）</li>
        <li><b>平滑移动</b>：鼠标以直线匀速滑到目标位置（200~400ms）</li>
        <li><b>人类模拟</b>：贝塞尔曲线 + 速度变化 + 微小抖动，最像真人</li>
    </ul>
    <p class="hint">注意：目标总时长 &lt; 5 秒时会强制使用"瞬移"。</p>

    <h5>抖动设置</h5>
    <ul>
        <li><b>人类模拟抖动</b>：模拟人类手抖的幅度（像素）</li>
        <li><b>点击抖动</b>：每次点击时随机偏移的幅度（像素）</li>
        <li>设 0 表示关闭该功能。</li>
    </ul>

    <h5>模板包</h5>
    <p>数字模板存放在 exe 同级的 <code>matchTemplates/</code> 文件夹中。</p>
    <p>支持的目录结构：</p>
    <ul>
        <li><b>单一字体</b>：<code>matchTemplates/1.png ~ 25.png</code></li>
        <li><b>多字体</b>：<code>matchTemplates/字体A/1.png ~ 25.png</code> 等</li>
    </ul>
    <p>每个模板包必须包含 1.png ~ 25.png 共 25 张图。如果 matchTemplates/ 文件夹不存在，程序会使用内置模板。</p>

    <h5>邀请码</h5>
    <p>目标总时长 &lt; 20 秒时需要输入邀请码。验证成功后会在 config.json 中保存授权标记，下次无需再次输入。</p>

    <h5>快捷键</h5>
    <ul>
        <li><b>F11</b>：切换全屏</li>
        <li><b>Esc</b>：关闭弹窗（选区时取消选区）</li>
    </ul>

    <h5>常见问题</h5>
    <ul>
        <li><b>识别不全</b>：重新选区，确保框选区域正好包含整个方格。</li>
        <li><b>点击位置偏移</b>：重新选区后重试。</li>
        <li><b>点击无效</b>：目标程序以管理员身份运行时，本程序也需要以管理员身份运行。</li>
        <li><b>杀毒软件报警</b>：PyInstaller 打包的程序常被误报，加入白名单即可。</li>
    </ul>

    <h5>免责声明</h5>
    <p class="hint">本工具仅供学习与自动化练习用途。请勿用于违反目标网站/程序使用条款的场景。使用者需自行承担使用行为带来的一切后果。</p>
</div>`;
    showModal({
        title: "使用说明",
        bodyHtml: helpHtml,
        showCancel: false,
        okText: "关闭",
    });
}

/* ============ 邀请码 ============ */
function askCode() {
    showModal({
        title: "需要邀请码",
        bodyHtml: `
            <p class="modal-text" style="color:#6b7280;">目标总时长 &lt; 20 秒，需要输入邀请码。</p>
            <input id="code-input" type="password" placeholder="输入邀请码" autocomplete="off">
        `,
        okText: "确定",
        onOk: async () => {
            const inp = document.getElementById("code-input");
            if (!inp) return false;
            const code = (inp.value || "").trim();
            if (!code) return false;
            const res = await pywebview.api.unlock_with_code(code);
            if (res && res.ok) {
                setTimeout(() => showAlert("成功", "邀请码已记住，再次点击\"开始点击\"即可运行。"), 100);
                return true;
            } else {
                inp.style.borderColor = "#ef4444";
                inp.value = "";
                inp.placeholder = "邀请码错误，请重试";
                return false;
            }
        },
    });
    setTimeout(() => {
        const inp = document.getElementById("code-input");
        if (inp) inp.focus();
    }, 50);
}