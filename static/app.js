// DSA Progress Tracker - Multi-User Client Logic

let state = {
    problems: [],
    plans: [],
    user: {
        username: "Coder",
        is_admin: false,
        dailyTarget: 3
    }
};

// Auth Mode state: 'login' or 'signup'
let authMode = 'login';

// Chart instances
let chartWeekly = null;
let chartTopic = null;

// Global DOM selectors
const elAuthBackdrop = document.getElementById("authBackdrop");
const elFormAuth = document.getElementById("formAuth");
const elAuthUsername = document.getElementById("authUsername");
const elAuthPassword = document.getElementById("authPassword");
const elAuthErrorMsg = document.getElementById("authErrorMsg");
const elBtnAuthSubmit = document.getElementById("btnAuthSubmit");
const elAuthToggleText = document.getElementById("authToggleText");
const elAuthToggleLink = document.getElementById("authToggleLink");
const elBtnLogOut = document.getElementById("btnLogOut");

// Profile elements
const elProfileMenuContainer = document.getElementById("profileMenuContainer");
const elBtnProfile = document.getElementById("btnProfile");
const elProfileDropdown = document.getElementById("profileDropdown");
const elProfileInitial = document.getElementById("profileInitial");
const elProfileInitialLarge = document.getElementById("profileInitialLarge");
const elProfileUsername = document.getElementById("profileUsername");
const elProfileDailyTarget = document.getElementById("profileDailyTarget");
const elProfileRole = document.getElementById("profileRole");

// Password strength element
const elPasswordStrengthWrapper = document.getElementById("passwordStrengthWrapper");
const elPasswordStrengthBar = document.getElementById("passwordStrengthBar");
const elPasswordStrengthText = document.getElementById("passwordStrengthText");

const elThemeToggle = document.getElementById("themeToggle");
const elUsernameDisplay = document.getElementById("usernameDisplay");
const elStatsTotalSolved = document.getElementById("statsTotalSolved");
const elStatsStreak = document.getElementById("statsStreak");
const elStatsMaxStreak = document.getElementById("statsMaxStreak");
const elDailyGoalCircle = document.getElementById("dailyGoalCircle");
const elDailyGoalFraction = document.getElementById("dailyGoalFraction");
const elDailyGoalPercent = document.getElementById("dailyGoalPercent");

const elCountEasy = document.getElementById("countEasy");
const elCountMedium = document.getElementById("countMedium");
const elCountHard = document.getElementById("countHard");
const elFillEasy = document.getElementById("fillEasy");
const elFillMedium = document.getElementById("fillMedium");
const elFillHard = document.getElementById("fillHard");

const elDistributionList = document.getElementById("distributionList");
const elBtnTabPlatforms = document.getElementById("btnTabPlatforms");
const elBtnTabTopics = document.getElementById("btnTabTopics");
let currentDistributionTab = "platforms";

const elHeatmapContainer = document.getElementById("heatmapContainer");
const elHeatmapContainerLarge = document.getElementById("heatmapContainerLarge");

const elAnalysisAvgWeekly = document.getElementById("analysisAvgWeekly");
const elAnalysisActiveDays = document.getElementById("analysisActiveDays");
const elAnalysisBestDay = document.getElementById("analysisBestDay");

const elPlansContainer = document.getElementById("plansContainer");
const elModalPlansCheckboxList = document.getElementById("modalPlansCheckboxList");

const elProblemsTableBody = document.getElementById("problemsTableBody");
const elProblemsEmptyState = document.getElementById("problemsEmptyState");
const elProblemsTable = document.getElementById("problemsTable");

const elFilterSearch = document.getElementById("filterSearch");
const elFilterDifficulty = document.getElementById("filterDifficulty");
const elFilterPlatform = document.getElementById("filterPlatform");
const elFilterTopic = document.getElementById("filterTopic");
const elBtnClearFilters = document.getElementById("btnClearFilters");

// Bulk Controls
const elSelectAllProblems = document.getElementById("selectAllProblems");
const elBtnBulkDelete = document.getElementById("btnBulkDelete");
const elBulkDeleteCount = document.getElementById("bulkDeleteCount");

// Admin Controls
const elNavItemAdmin = document.getElementById("navItemAdmin");
const elAdminTotalUsers = document.getElementById("adminTotalUsers");
const elAdminTotalProblems = document.getElementById("adminTotalProblems");
const elAdminUsersTableBody = document.getElementById("adminUsersTableBody");

// Modals
const elModalLogProblem = document.getElementById("modalLogProblem");
const elFormLogProblem = document.getElementById("formLogProblem");
const elEditProblemId = document.getElementById("editProblemId");
const elProblemName = document.getElementById("problemName");
const elProblemDifficulty = document.getElementById("problemDifficulty");
const elProblemPlatform = document.getElementById("problemPlatform");
const elProblemTopic = document.getElementById("problemTopic");
const elProblemDate = document.getElementById("problemDate");
const elProblemUrl = document.getElementById("problemUrl");
const elProblemNotes = document.getElementById("problemNotes");

const elModalCreatePlan = document.getElementById("modalCreatePlan");
const elFormCreatePlan = document.getElementById("formCreatePlan");

const elModalSettings = document.getElementById("modalSettings");
const elFormSettings = document.getElementById("formSettings");
const elResetScope = document.getElementById("resetScope");
const elBtnResetProgress = document.getElementById("btnResetProgress");

const elModalResetPassword = document.getElementById("modalResetPassword");
const elFormResetPassword = document.getElementById("formResetPassword");

// Navigation tabs
const elNavItems = document.querySelectorAll(".nav-item");
const elTabContents = document.querySelectorAll(".tab-content");

// Tooltip DOM
let elTooltip = document.getElementById("appTooltip");
if (!elTooltip) {
    elTooltip = document.createElement("div");
    elTooltip.id = "appTooltip";
    elTooltip.className = "tooltip";
    document.body.appendChild(elTooltip);
}

// -------------------------------------------------------------
// API Request Helper
// -------------------------------------------------------------
async function apiRequest(url, options = {}) {
    options.headers = options.headers || {};
    options.headers['Content-Type'] = 'application/json';
    options.credentials = 'include'; // Make sure cookies are sent
    
    try {
        const response = await fetch(url, options);
        const data = await response.json();
        
        if (!response.ok) {
            // Handle unauthorized redirects
            if (response.status === 401 && url !== '/api/auth/status') {
                showAuthBackdrop();
            }
            throw new Error(data.error || 'Server error occurred');
        }
        return data;
    } catch (err) {
        console.error("API Error:", err.message);
        throw err;
    }
}

// -------------------------------------------------------------
// Auth Flow Handlers
// -------------------------------------------------------------
function showAuthBackdrop() {
    elAuthBackdrop.classList.add("show");
    setAuthMode('login'); // Always default to Login mode
}

function hideAuthBackdrop() {
    elAuthBackdrop.classList.remove("show");
}

function setAuthMode(mode) {
    authMode = mode;
    elAuthErrorMsg.style.display = "none";
    elPasswordStrengthWrapper.style.display = "none";
    elAuthPassword.value = "";
    
    const elAuthEmail = document.getElementById("authEmail");
    if (elAuthEmail) elAuthEmail.value = "";
    
    const signupFields = document.querySelectorAll(".signup-only");
    signupFields.forEach(el => {
        el.style.display = authMode === 'signup' ? 'block' : 'none';
        const input = el.querySelector('input');
        if (input) {
            input.required = authMode === 'signup';
        }
    });
    
    if (authMode === 'login') {
        document.querySelector(".auth-header h2").textContent = "DSA Tracker Login";
        document.getElementById("authSubtitle").textContent = "Log in to track algorithms and sync progress.";
        elBtnAuthSubmit.textContent = "Log In";
        elAuthToggleText.textContent = "Don't have an account?";
        elAuthToggleLink.textContent = "Sign Up";
        const forgotContainer = document.getElementById("authForgotLinkContainer");
        if (forgotContainer) forgotContainer.style.display = "block";
    } else {
        document.querySelector(".auth-header h2").textContent = "DSA Tracker Sign Up";
        document.getElementById("authSubtitle").textContent = "Register a new coder account to track DSA tasks.";
        elBtnAuthSubmit.textContent = "Create Account";
        elAuthToggleText.textContent = "Already have an account?";
        elAuthToggleLink.textContent = "Log In";
        const forgotContainer = document.getElementById("authForgotLinkContainer");
        if (forgotContainer) forgotContainer.style.display = "none";
    }
}

function checkPasswordStrength(password) {
    let score = 0;
    if (password.length >= 6) score++;
    if (password.length >= 8) score++;
    if (/[a-zA-Z]/.test(password)) score++;
    if (/[0-9]/.test(password)) score++;
    if (/[^a-zA-Z0-9]/.test(password)) score++;
    
    if (score <= 2) return "Weak";
    if (score <= 4) return "Medium";
    return "Strong";
}

function updatePasswordStrengthUI(strength) {
    elPasswordStrengthText.textContent = strength;
    if (strength === "Weak") {
        elPasswordStrengthBar.style.width = "33%";
        elPasswordStrengthBar.style.backgroundColor = "var(--rose)";
        elPasswordStrengthText.style.color = "var(--rose)";
    } else if (strength === "Medium") {
        elPasswordStrengthBar.style.width = "66%";
        elPasswordStrengthBar.style.backgroundColor = "var(--amber)";
        elPasswordStrengthText.style.color = "var(--amber)";
    } else {
        elPasswordStrengthBar.style.width = "100%";
        elPasswordStrengthBar.style.backgroundColor = "var(--emerald)";
        elPasswordStrengthText.style.color = "var(--emerald)";
    }
}

async function checkAuthStatus() {
    try {
        const status = await apiRequest('/api/auth/status');
        if (status.authenticated) {
            state.user.username = status.user.username;
            state.user.is_admin = status.user.is_admin;
            state.user.dailyTarget = status.user.daily_target;
            
            // Show Admin controls if admin
            if (state.user.is_admin) {
                elNavItemAdmin.style.display = "flex";
            } else {
                elNavItemAdmin.style.display = "none";
            }
            
            // Update profile info elements
            const initial = state.user.username.charAt(0).toUpperCase();
            elProfileInitial.textContent = initial;
            elProfileInitialLarge.textContent = initial;
            elProfileUsername.textContent = state.user.username;
            elProfileDailyTarget.textContent = `${state.user.dailyTarget} / day`;
            elProfileRole.textContent = state.user.is_admin ? "Administrator" : "Coder Account";
            
            hideAuthBackdrop();
            await fetchAllUserData();
        } else {
            showAuthBackdrop();
        }
    } catch (err) {
        showAuthBackdrop();
    }
}

async function fetchAllUserData() {
    try {
        const problems = await apiRequest('/api/problems');
        const plans = await apiRequest('/api/plans');
        
        state.problems = problems;
        state.plans = plans;
        
        updateUI();
    } catch (err) {
        console.error("Failed to load user progress:", err.message);
    }
}

// -------------------------------------------------------------
// Initialize App
// -------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    // Read saved theme
    const savedTheme = localStorage.getItem("dsa_tracker_theme") || "dark";
    applyTheme(savedTheme);
    
    setupEventListeners();
    checkAuthStatus();
});

// -------------------------------------------------------------
// Core UI Update Router
// -------------------------------------------------------------
function updateUI() {
    // Header welcome
    elUsernameDisplay.textContent = state.user.username || "Coder";

    // Dashboard
    updateDashboardStats();
    updateDifficultyBreakdown();
    updatePerformanceDistribution();
    updateHeatmaps();
    
    // Study plans
    updateStudyPlans();
    
    // Dropdowns filters
    updateFiltersDatalists();
    updateProblemsLogTable();
    
    // Charts (Chart.js integration)
    renderCharts();
}

// -------------------------------------------------------------
// Theme Management
// -------------------------------------------------------------
function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("dsa_tracker_theme", theme);
}

// -------------------------------------------------------------
// Tab Selectors
// -------------------------------------------------------------
elNavItems.forEach(item => {
    item.addEventListener("click", async (e) => {
        e.preventDefault();
        const targetTab = item.getAttribute("data-tab");

        elNavItems.forEach(n => n.classList.remove("active"));
        item.classList.add("active");

        elTabContents.forEach(content => {
            if (content.id === `section-${targetTab}`) {
                content.classList.add("active");
            } else {
                content.classList.remove("active");
            }
        });

        // Trigger custom tab content updates
        if (targetTab === 'admin') {
            await loadAdminStats();
        }
    });
});

// -------------------------------------------------------------
// Stats & Streak calculations
// -------------------------------------------------------------
function getTodayString() {
    return new Date().toISOString().split('T')[0];
}

function getYesterdayString() {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    return d.toISOString().split('T')[0];
}

function calculateStreak(problems) {
    if (!problems || problems.length === 0) return { current: 0, max: 0 };

    // Get unique solve dates sorted descending
    const dates = [...new Set(problems.map(p => p.date))].sort((a, b) => new Date(b) - new Date(a));
    const today = getTodayString();
    const yesterday = getYesterdayString();

    let currentStreak = 0;
    let maxStreak = 0;
    
    const hasToday = dates.includes(today);
    const hasYesterday = dates.includes(yesterday);

    if (hasToday || hasYesterday) {
        let currentRef = hasToday ? new Date(today) : new Date(yesterday);
        currentStreak = 1;
        
        let i = dates.indexOf(currentRef.toISOString().split('T')[0]);
        if (i !== -1) {
            let expectedDate = new Date(currentRef);
            while (true) {
                expectedDate.setDate(expectedDate.getDate() - 1);
                const expectedStr = expectedDate.toISOString().split('T')[0];
                if (dates.includes(expectedStr)) {
                    currentStreak++;
                } else {
                    break;
                }
            }
        }
    }

    const ascendingDates = [...dates].reverse();
    if (ascendingDates.length > 0) {
        let tempStreak = 1;
        maxStreak = 1;
        for (let i = 1; i < ascendingDates.length; i++) {
            const prev = new Date(ascendingDates[i - 1]);
            const curr = new Date(ascendingDates[i]);
            const diffTime = Math.abs(curr - prev);
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            
            if (diffDays === 1) {
                tempStreak++;
                maxStreak = Math.max(maxStreak, tempStreak);
            } else if (diffDays > 1) {
                tempStreak = 1;
            }
        }
    }

    return { current: currentStreak, max: maxStreak };
}

function updateDashboardStats() {
    const totalCount = state.problems.length;
    elStatsTotalSolved.textContent = totalCount;

    const streaks = calculateStreak(state.problems);
    elStatsStreak.textContent = streaks.current;
    elStatsMaxStreak.textContent = streaks.max;

    const todayStr = getTodayString();
    const solvedToday = state.problems.filter(p => p.date === todayStr).length;
    const dailyTarget = state.user.dailyTarget || 3;

    elDailyGoalFraction.textContent = `${solvedToday}/${dailyTarget}`;
    
    const percentage = Math.min(100, Math.round((solvedToday / dailyTarget) * 100));
    elDailyGoalPercent.textContent = `${percentage}%`;
    elDailyGoalCircle.setAttribute("stroke-dasharray", `${percentage}, 100`);
}

// -------------------------------------------------------------
// Difficulty breakdowns
// -------------------------------------------------------------
function updateDifficultyBreakdown() {
    const total = state.problems.length;
    if (total === 0) {
        elCountEasy.textContent = 0;
        elCountMedium.textContent = 0;
        elCountHard.textContent = 0;
        elFillEasy.style.width = "0%";
        elFillMedium.style.width = "0%";
        elFillHard.style.width = "0%";
        return;
    }

    const easy = state.problems.filter(p => p.difficulty === "Easy").length;
    const medium = state.problems.filter(p => p.difficulty === "Medium").length;
    const hard = state.problems.filter(p => p.difficulty === "Hard").length;

    elCountEasy.textContent = easy;
    elCountMedium.textContent = medium;
    elCountHard.textContent = hard;

    elFillEasy.style.width = `${(easy / total) * 100}%`;
    elFillMedium.style.width = `${(medium / total) * 100}%`;
    elFillHard.style.width = `${(hard / total) * 100}%`;
}

function updatePerformanceDistribution() {
    const listContainer = elDistributionList;
    listContainer.innerHTML = "";

    const frequencies = {};
    const total = state.problems.length;

    if (total === 0) {
        listContainer.innerHTML = `<div class="empty-state">No distribution data logged yet.</div>`;
        return;
    }

    if (currentDistributionTab === "platforms") {
        state.problems.forEach(p => {
            frequencies[p.platform] = (frequencies[p.platform] || 0) + 1;
        });
    } else {
        state.problems.forEach(p => {
            frequencies[p.topic] = (frequencies[p.topic] || 0) + 1;
        });
    }

    const sorted = Object.entries(frequencies).sort((a, b) => b[1] - a[1]);

    sorted.forEach(([label, val]) => {
        const percent = Math.round((val / total) * 100);
        const item = document.createElement("div");
        item.className = "dist-item";
        item.innerHTML = `
            <span class="dist-label">${label}</span>
            <div class="dist-progress-box">
                <div class="dist-track">
                    <div class="dist-fill" style="width: ${percent}%"></div>
                </div>
                <span class="dist-val">${val}</span>
            </div>
        `;
        listContainer.appendChild(item);
    });
}

// -------------------------------------------------------------
// Heatmap Rendering
// -------------------------------------------------------------
function updateHeatmaps() {
    renderHeatmapInContainer(elHeatmapContainer);
    renderHeatmapInContainer(elHeatmapContainerLarge);
    updateHeatmapAnalysis();
}

function renderHeatmapInContainer(container) {
    if (!container) return;
    container.innerHTML = "";

    const today = new Date();
    const start = new Date(today);
    start.setDate(today.getDate() - 364);
    const dayOfWeek = start.getDay();
    start.setDate(start.getDate() - dayOfWeek); // Sunday align

    const dateCounts = {};
    state.problems.forEach(p => {
        dateCounts[p.date] = (dateCounts[p.date] || 0) + 1;
    });

    const dateIter = new Date(start);
    const cells = [];

    while (dateIter <= today) {
        const dateStr = dateIter.toISOString().split('T')[0];
        const count = dateCounts[dateStr] || 0;
        
        let level = 0;
        if (count === 1) level = 1;
        else if (count === 2) level = 2;
        else if (count === 3) level = 3;
        else if (count > 3) level = 4;

        cells.push({ date: dateStr, count, level });
        dateIter.setDate(dateIter.getDate() + 1);
    }

    cells.forEach(cell => {
        const dayCell = document.createElement("div");
        dayCell.className = `heatmap-day level-${cell.level}`;
        dayCell.setAttribute("data-date", cell.date);
        dayCell.setAttribute("data-count", cell.count);

        dayCell.addEventListener("mouseover", (e) => {
            const formattedDate = new Date(cell.date).toLocaleDateString(undefined, {
                month: 'short', day: 'numeric', year: 'numeric'
            });
            const text = `${cell.count} problem${cell.count !== 1 ? 's' : ''} solved on ${formattedDate}`;
            showTooltip(e, text);
        });

        dayCell.addEventListener("mousemove", (e) => moveTooltip(e));
        dayCell.addEventListener("mouseout", () => hideTooltip());
        container.appendChild(dayCell);
    });
}

function updateHeatmapAnalysis() {
    const totalCount = state.problems.length;
    if (totalCount === 0) {
        elAnalysisAvgWeekly.textContent = "0.0";
        elAnalysisActiveDays.textContent = "0 days";
        elAnalysisBestDay.textContent = "None";
        return;
    }

    const dates = [...new Set(state.problems.map(p => p.date))];
    elAnalysisActiveDays.textContent = `${dates.length} days`;

    const today = new Date();
    const minDateStr = state.problems.reduce((min, p) => p.date < min ? p.date : min, today.toISOString().split('T')[0]);
    const minDate = new Date(minDateStr);
    const diffTime = Math.abs(today - minDate);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) || 1;
    const weeks = Math.max(1, diffDays / 7);
    elAnalysisAvgWeekly.textContent = (totalCount / weeks).toFixed(1);

    const dateCounts = {};
    state.problems.forEach(p => {
        dateCounts[p.date] = (dateCounts[p.date] || 0) + 1;
    });
    const sortedDates = Object.entries(dateCounts).sort((a, b) => b[1] - a[1]);
    if (sortedDates.length > 0) {
        const [bestDateStr, maxCount] = sortedDates[0];
        const formatted = new Date(bestDateStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
        elAnalysisBestDay.textContent = `${formatted} (${maxCount})`;
    } else {
        elAnalysisBestDay.textContent = "None";
    }
}

// Tooltip helpers
function showTooltip(e, text) {
    elTooltip.textContent = text;
    elTooltip.classList.add("show");
    moveTooltip(e);
}

function moveTooltip(e) {
    const padding = 15;
    elTooltip.style.left = `${e.pageX + padding}px`;
    elTooltip.style.top = `${e.pageY - padding}px`;
}

function hideTooltip() {
    elTooltip.classList.remove("show");
}

// -------------------------------------------------------------
// Custom Study Plans
// -------------------------------------------------------------
function updateStudyPlans() {
    const container = elPlansContainer;
    const checkboxList = elModalPlansCheckboxList;

    container.innerHTML = "";
    checkboxList.innerHTML = "";

    if (state.plans.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
                </div>
                <h4>No active study plans yet</h4>
                <p>Create a plan to group problems and track focused progress.</p>
                <button class="btn btn-primary" id="btnCreatePlanEmpty">Create First Plan</button>
            </div>
        `;
        document.getElementById("btnCreatePlanEmpty")?.addEventListener("click", () => openModal(elModalCreatePlan));
        checkboxList.innerHTML = `<span class="small-text-gray">No active study plans. Create one first!</span>`;
        return;
    }

    state.plans.forEach(plan => {
        const matchedProblemsCount = state.problems.filter(p => p.plans && p.plans.includes(plan.id)).length;
        const progressPercent = Math.min(100, Math.round((matchedProblemsCount / plan.targetCount) * 100));

        const planCard = document.createElement("div");
        planCard.className = "card plan-card";
        planCard.style.borderLeftColor = plan.color;
        planCard.innerHTML = `
            <div>
                <div class="plan-title-row">
                    <h3>${plan.title}</h3>
                    <button class="plan-delete-btn" data-id="${plan.id}" title="Delete Study Plan">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </button>
                </div>
                <p>${plan.description || 'No description provided.'}</p>
            </div>
            <div class="plan-progress-wrapper">
                <div class="plan-progress-header">
                    <span>${progressPercent}% Complete</span>
                    <span>${matchedProblemsCount}/${plan.targetCount} Solved</span>
                </div>
                <div class="plan-progress-track">
                    <div class="plan-progress-fill" style="width: ${progressPercent}%; background-color: ${plan.color};"></div>
                </div>
            </div>
        `;

        planCard.querySelector(".plan-delete-btn").addEventListener("click", async (e) => {
            e.stopPropagation();
            if (confirm(`Are you sure you want to delete the plan "${plan.title}"?`)) {
                await deletePlan(plan.id);
            }
        });

        container.appendChild(planCard);

        const label = document.createElement("label");
        label.className = "checkbox-item";
        label.innerHTML = `
            <input type="checkbox" name="associatedPlans" value="${plan.id}">
            <span>${plan.title}</span>
        `;
        checkboxList.appendChild(label);
    });
}

async function deletePlan(planId) {
    try {
        await apiRequest(`/api/plans/${planId}`, { method: 'DELETE' });
        await fetchAllUserData();
    } catch (err) {
        alert(err.message);
    }
}

// -------------------------------------------------------------
// Filters & Tables logs
// -------------------------------------------------------------
function updateFiltersDatalists() {
    const platforms = [...new Set(state.problems.map(p => p.platform))].sort();
    const prevPlatformVal = elFilterPlatform.value;
    elFilterPlatform.innerHTML = `<option value="all">All Platforms</option>`;
    platforms.forEach(plat => {
        elFilterPlatform.innerHTML += `<option value="${plat}">${plat}</option>`;
    });
    if (platforms.includes(prevPlatformVal)) {
        elFilterPlatform.value = prevPlatformVal;
    }

    const topics = [...new Set(state.problems.map(p => p.topic))].sort();
    const prevTopicVal = elFilterTopic.value;
    elFilterTopic.innerHTML = `<option value="all">All Topics</option>`;
    topics.forEach(top => {
        elFilterTopic.innerHTML += `<option value="${top}">${top}</option>`;
    });
    if (topics.includes(prevTopicVal)) {
        elFilterTopic.value = prevTopicVal;
    }
}

function updateProblemsLogTable() {
    const tableBody = elProblemsTableBody;
    tableBody.innerHTML = "";
    
    if (elSelectAllProblems) {
        elSelectAllProblems.checked = false;
    }
    if (elBtnBulkDelete) {
        elBtnBulkDelete.style.display = "none";
    }

    const query = elFilterSearch.value.toLowerCase().trim();
    const difficultyFilter = elFilterDifficulty.value;
    const platformFilter = elFilterPlatform.value;
    const topicFilter = elFilterTopic.value;

    const filtered = state.problems.filter(p => {
        const matchQuery = !query || 
            p.name.toLowerCase().includes(query) || 
            (p.notes && p.notes.toLowerCase().includes(query)) ||
            p.topic.toLowerCase().includes(query) ||
            p.platform.toLowerCase().includes(query);

        const matchDiff = difficultyFilter === "all" || p.difficulty === difficultyFilter;
        const matchPlatform = platformFilter === "all" || p.platform === platformFilter;
        const matchTopic = topicFilter === "all" || p.topic === topicFilter;

        return matchQuery && matchDiff && matchPlatform && matchTopic;
    });

    filtered.sort((a, b) => new Date(b.date) - new Date(a.date));

    if (filtered.length === 0) {
        elProblemsTable.style.display = "none";
        elProblemsEmptyState.style.display = "flex";
        return;
    }

    elProblemsTable.style.display = "table";
    elProblemsEmptyState.style.display = "none";

    filtered.forEach(p => {
        const tr = document.createElement("tr");
        const dateFormatted = new Date(p.date).toLocaleDateString(undefined, {
            month: 'short', day: 'numeric', year: 'numeric'
        });
        const diffBadge = `<span class="badge badge-${p.difficulty.toLowerCase()}">${p.difficulty}</span>`;
        const nameDisplay = p.url 
            ? `<a href="${p.url}" target="_blank" rel="noopener noreferrer" class="problem-link-anchor">
                <span>${p.name}</span>
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
               </a>`
            : `<span class="font-semibold">${p.name}</span>`;

        tr.innerHTML = `
            <td>
                <input type="checkbox" class="problem-select-checkbox" data-id="${p.id}" style="cursor: pointer; width: 16px; height: 16px; margin-top: 3px;">
            </td>
            <td>
                <div>
                    ${nameDisplay}
                    ${p.notes ? `<p class="small-text-gray" style="margin-top:4px; font-weight:normal; max-width:300px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${p.notes.replace(/"/g, '&quot;')}">${p.notes}</p>` : ''}
                </div>
            </td>
            <td><span class="small-text-gray" style="font-weight:600;">${p.topic}</span></td>
            <td>${diffBadge}</td>
            <td><span class="small-text-gray" style="font-weight:600;">${p.platform}</span></td>
            <td><span class="small-text-gray">${dateFormatted}</span></td>
            <td>
                <div class="actions-cell">
                    <button class="btn-icon edit" data-id="${p.id}" title="Edit Problem">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                    </button>
                    <button class="btn-icon delete" data-id="${p.id}" title="Delete Problem Log">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </button>
                </div>
            </td>
        `;

        tr.querySelector(".problem-select-checkbox").addEventListener("change", () => {
            updateBulkDeleteButtonState();
        });
        tr.querySelector(".edit").addEventListener("click", () => editProblem(p.id));
        tr.querySelector(".delete").addEventListener("click", async () => {
            if (confirm(`Delete problem log for "${p.name}"?`)) {
                await deleteProblem(p.id);
            }
        });

        tableBody.appendChild(tr);
    });
}

async function deleteProblem(id) {
    try {
        await apiRequest(`/api/problems/${id}`, { method: 'DELETE' });
        await fetchAllUserData();
    } catch (err) {
        alert(err.message);
    }
}

function editProblem(id) {
    const p = state.problems.find(prob => prob.id === id);
    if (!p) return;

    elEditProblemId.value = p.id;
    elProblemName.value = p.name;
    elProblemDifficulty.value = p.difficulty;
    elProblemPlatform.value = p.platform;
    elProblemTopic.value = p.topic;
    elProblemDate.value = p.date;
    elProblemUrl.value = p.url || "";
    elProblemNotes.value = p.notes || "";

    document.getElementById("modalLogTitle").textContent = "Edit Solved Problem";
    openModal(elModalLogProblem);

    const checkboxes = elFormLogProblem.querySelectorAll("input[name='associatedPlans']");
    checkboxes.forEach(cb => {
        cb.checked = p.plans && p.plans.includes(cb.value);
    });
}

// -------------------------------------------------------------
// Interactive Charts Rendering (Chart.js)
// -------------------------------------------------------------
function renderCharts() {
    const theme = document.documentElement.getAttribute("data-theme") || 'dark';
    const isDark = theme === 'dark';
    
    // Theme configurations
    const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
    const textColor = isDark ? '#8e9bb0' : '#718096';

    // 1. Render Weekly Chart
    // Get last 7 days names and counts
    const weeklyLabels = [];
    const weeklyCounts = [];
    
    const dateCounts = {};
    state.problems.forEach(p => {
        dateCounts[p.date] = (dateCounts[p.date] || 0) + 1;
    });

    for (let i = 6; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        const dateStr = d.toISOString().split('T')[0];
        const label = d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' });
        weeklyLabels.push(label);
        weeklyCounts.push(dateCounts[dateStr] || 0);
    }

    if (chartWeekly) chartWeekly.destroy();
    
    const ctxWeekly = document.getElementById("chartWeeklyProgress").getContext("2d");
    chartWeekly = new Chart(ctxWeekly, {
        type: 'line',
        data: {
            labels: weeklyLabels,
            datasets: [{
                label: 'Solves',
                data: weeklyCounts,
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99,102,241,0.15)',
                borderWidth: 2.5,
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: gridColor }, ticks: { color: textColor, font: { family: 'Outfit' } } },
                y: { grid: { color: gridColor }, ticks: { color: textColor, stepSize: 1, font: { family: 'Outfit' } } }
            }
        }
    });

    // 2. Render Topic Breakdown Chart
    const topicsMap = {};
    state.problems.forEach(p => {
        topicsMap[p.topic] = (topicsMap[p.topic] || 0) + 1;
    });
    
    // Sort and slice top 5
    const topTopics = Object.entries(topicsMap)
        .sort((a,b) => b[1] - a[1])
        .slice(0, 5);

    const topicLabels = topTopics.map(t => t[0]);
    const topicCounts = topTopics.map(t => t[1]);

    if (chartTopic) chartTopic.destroy();

    const ctxTopic = document.getElementById("chartTopicProgress").getContext("2d");
    chartTopic = new Chart(ctxTopic, {
        type: 'doughnut',
        data: {
            labels: topicLabels,
            datasets: [{
                data: topicCounts,
                backgroundColor: [
                    '#6366f1', '#10b981', '#f59e0b', '#ef4444', '#0ea5e9'
                ],
                borderWidth: isDark ? 2 : 1,
                borderColor: isDark ? '#0f1524' : '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: textColor, font: { family: 'Outfit', size: 11 } }
                }
            }
        }
    });
}

// -------------------------------------------------------------
// Admin Controls Loader
// -------------------------------------------------------------
async function loadAdminStats() {
    try {
        const data = await apiRequest('/api/admin/stats');
        elAdminTotalUsers.textContent = data.total_users;
        elAdminTotalProblems.textContent = data.total_problems;

        const body = elAdminUsersTableBody;
        body.innerHTML = "";

        data.users.forEach(u => {
            const tr = document.createElement("tr");
            const regDate = new Date(u.created_at).toLocaleDateString(undefined, {
                month: 'short', day: 'numeric', year: 'numeric'
            });
            const role = u.is_admin ? `<span class="badge badge-easy">Admin</span>` : `<span class="badge" style="background-color:rgba(100,116,139,0.1); color:var(--text-muted)">Coder</span>`;
            
            tr.innerHTML = `
                <td><span style="font-weight: 700;">${u.username}</span></td>
                <td>${role}</td>
                <td><span class="small-text-gray">${regDate}</span></td>
                <td><span style="font-weight: 600; color: var(--indigo);">${u.solved_count}</span> problems</td>
            `;
            body.appendChild(tr);
        });
    } catch (err) {
        console.error("Failed to load admin logs:", err.message);
    }
}

// -------------------------------------------------------------
// Modals open/close
// -------------------------------------------------------------
function openModal(modal) {
    modal.classList.add("show");
}

function closeModal(modal) {
    modal.classList.remove("show");
}

// -------------------------------------------------------------
// Event Listeners Binding
// -------------------------------------------------------------
function setupEventListeners() {
    // Auth Mode Toggler
    elAuthToggleLink.addEventListener("click", (e) => {
        e.preventDefault();
        setAuthMode(authMode === 'login' ? 'signup' : 'login');
    });

    // Password strength check on input
    elAuthPassword.addEventListener("input", () => {
        if (authMode !== 'signup') {
            elPasswordStrengthWrapper.style.display = "none";
            return;
        }
        const val = elAuthPassword.value;
        if (!val) {
            elPasswordStrengthWrapper.style.display = "none";
            return;
        }
        elPasswordStrengthWrapper.style.display = "block";
        const strength = checkPasswordStrength(val);
        updatePasswordStrengthUI(strength);
    });

    // Toggle Password Visibility (Eye Icon)
    const elBtnTogglePassword = document.getElementById("btnTogglePassword");
    if (elBtnTogglePassword) {
        elBtnTogglePassword.addEventListener("click", () => {
            const type = elAuthPassword.getAttribute("type") === "password" ? "text" : "password";
            elAuthPassword.setAttribute("type", type);
            const eyeOpen = elBtnTogglePassword.querySelector(".eye-open");
            const eyeClosed = elBtnTogglePassword.querySelector(".eye-closed");
            if (type === "password") {
                if (eyeOpen) eyeOpen.style.display = "block";
                if (eyeClosed) eyeClosed.style.display = "none";
            } else {
                if (eyeOpen) eyeOpen.style.display = "none";
                if (eyeClosed) eyeClosed.style.display = "block";
            }
        });
    }

    // Send Signup Verification Code
    const elBtnSendSignupCode = document.getElementById("btnSendSignupCode");
    let signupTimer = null;
    if (elBtnSendSignupCode) {
        elBtnSendSignupCode.addEventListener("click", async () => {
            const username = elAuthUsername.value.trim();
            const email = document.getElementById("authEmail").value.trim();
            
            if (!username) {
                alert("Please enter a username first.");
                return;
            }
            const target = email;
            if (!target) {
                alert("Please enter an email address to receive the verification code.");
                return;
            }
            
            try {
                elBtnSendSignupCode.disabled = true;
                const res = await apiRequest('/api/auth/send-code', {
                    method: 'POST',
                    body: JSON.stringify({ username, target, purpose: 'signup' })
                });
                if (res && res.sent_real) {
                    alert(`Verification code sent to ${target}. Please check your inbox!`);
                } else {
                    alert(`[Dev Mode] Verification code printed to the server terminal console log.`);
                }
                
                let secondsLeft = 30;
                elBtnSendSignupCode.textContent = `Resend in ${secondsLeft}s`;
                if (signupTimer) clearInterval(signupTimer);
                signupTimer = setInterval(() => {
                    secondsLeft--;
                    if (secondsLeft <= 0) {
                        clearInterval(signupTimer);
                        elBtnSendSignupCode.disabled = false;
                        elBtnSendSignupCode.textContent = "Resend Code";
                    } else {
                        elBtnSendSignupCode.textContent = `Resend in ${secondsLeft}s`;
                    }
                }, 1000);
            } catch (err) {
                alert(err.message);
                elBtnSendSignupCode.disabled = false;
            }
        });
    }

    // Auth Submission
    elFormAuth.addEventListener("submit", async (e) => {
        e.preventDefault();
        const username = elAuthUsername.value.trim();
        const password = elAuthPassword.value;
        
        elAuthErrorMsg.style.display = "none";
        
        const payload = { username, password };
        if (authMode === 'signup') {
            const elAuthEmail = document.getElementById("authEmail");
            const elAuthCode = document.getElementById("authCode");
            payload.email = elAuthEmail ? elAuthEmail.value.trim() : "";
            payload.code = elAuthCode ? elAuthCode.value.trim() : "";
        }
        
        const url = authMode === 'login' ? '/api/auth/login' : '/api/auth/signup';
        try {
            await apiRequest(url, {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            elFormAuth.reset();
            if (signupTimer) {
                clearInterval(signupTimer);
                signupTimer = null;
            }
            if (elBtnSendSignupCode) {
                elBtnSendSignupCode.disabled = false;
                elBtnSendSignupCode.textContent = "Send Code";
            }
            await checkAuthStatus();
        } catch (err) {
            elAuthErrorMsg.textContent = err.message;
            elAuthErrorMsg.style.display = "block";
        }
    });

    // Profile menu toggle dropdown
    elBtnProfile.addEventListener("click", (e) => {
        e.stopPropagation();
        elProfileDropdown.classList.toggle("show");
    });

    // Close profile dropdown on clicking outside
    document.addEventListener("click", (e) => {
        if (elProfileMenuContainer && !elProfileMenuContainer.contains(e.target)) {
            elProfileDropdown.classList.remove("show");
        }
    });

    // Logout Button
    elBtnLogOut.addEventListener("click", async () => {
        if (confirm("Are you sure you want to log out?")) {
            try {
                await apiRequest('/api/auth/logout', { method: 'POST' });
                // Reset state
                state.problems = [];
                state.plans = [];
                state.user = { username: "Coder", is_admin: false, dailyTarget: 3 };
                
                // Clear charts
                if (chartWeekly) chartWeekly.destroy();
                if (chartTopic) chartTopic.destroy();
                
                elProfileDropdown.classList.remove("show");
                showAuthBackdrop();
            } catch (err) {
                console.error("Logout failed:", err.message);
            }
        }
    });

    // Reset Password Modal Trigger
    const elResetPasswordUsername = document.getElementById("resetPasswordUsername");
    const elResetPasswordVerification = document.getElementById("resetPasswordVerification");
    const elResetPasswordCode = document.getElementById("resetPasswordCode");
    const elResetPasswordNew = document.getElementById("resetPasswordNew");
    const elResetPasswordErrorMsg = document.getElementById("resetPasswordErrorMsg");
    const elAuthForgotLink = document.getElementById("authForgotLink");

    const elBtnSendResetCode = document.getElementById("btnSendResetCode");
    let resetTimer = null;

    const clearResetTimer = () => {
        if (resetTimer) {
            clearInterval(resetTimer);
            resetTimer = null;
        }
        if (elBtnSendResetCode) {
            elBtnSendResetCode.disabled = false;
            elBtnSendResetCode.textContent = "Send Code";
        }
    };

    const elBtnProfileResetPassword = document.getElementById("btnProfileResetPassword");
    if (elBtnProfileResetPassword) {
        elBtnProfileResetPassword.addEventListener("click", () => {
            elFormResetPassword.reset();
            clearResetTimer();
            elResetPasswordErrorMsg.style.display = "none";
            document.getElementById("resetPasswordStrengthWrapper").style.display = "none";
            elProfileDropdown.classList.remove("show");
            if (state.user && state.user.username && state.user.username !== "Coder") {
                elResetPasswordUsername.value = state.user.username;
            }
            openModal(elModalResetPassword);
        });
    }
    if (elAuthForgotLink) {
        elAuthForgotLink.addEventListener("click", (e) => {
            e.preventDefault();
            elFormResetPassword.reset();
            clearResetTimer();
            elResetPasswordErrorMsg.style.display = "none";
            document.getElementById("resetPasswordStrengthWrapper").style.display = "none";
            openModal(elModalResetPassword);
        });
    }
    const elBtnCloseResetPasswordModal = document.getElementById("btnCloseResetPasswordModal");
    if (elBtnCloseResetPasswordModal) {
        elBtnCloseResetPasswordModal.addEventListener("click", () => {
            closeModal(elModalResetPassword);
            clearResetTimer();
        });
    }
    const elBtnCancelResetPasswordModal = document.getElementById("btnCancelResetPasswordModal");
    if (elBtnCancelResetPasswordModal) {
        elBtnCancelResetPasswordModal.addEventListener("click", () => {
            closeModal(elModalResetPassword);
            clearResetTimer();
        });
    }

    // Send Reset Verification Code
    if (elBtnSendResetCode) {
        elBtnSendResetCode.addEventListener("click", async () => {
            const username = elResetPasswordUsername.value.trim();
            const target = elResetPasswordVerification.value.trim();
            
            if (!username) {
                alert("Please enter your username first.");
                return;
            }
            if (!target) {
                alert("Please enter your registered email address.");
                return;
            }
            
            try {
                elBtnSendResetCode.disabled = true;
                const res = await apiRequest('/api/auth/send-code', {
                    method: 'POST',
                    body: JSON.stringify({ username, target, purpose: 'reset' })
                });
                if (res && res.sent_real) {
                    alert(`Verification code sent to ${target}. Please check your inbox!`);
                } else {
                    alert(`[Dev Mode] Verification code printed to the server terminal console log.`);
                }
                
                let secondsLeft = 30;
                elBtnSendResetCode.textContent = `Resend in ${secondsLeft}s`;
                if (resetTimer) clearInterval(resetTimer);
                resetTimer = setInterval(() => {
                    secondsLeft--;
                    if (secondsLeft <= 0) {
                        clearInterval(resetTimer);
                        elBtnSendResetCode.disabled = false;
                        elBtnSendResetCode.textContent = "Resend Code";
                    } else {
                        elBtnSendResetCode.textContent = `Resend in ${secondsLeft}s`;
                    }
                }, 1000);
            } catch (err) {
                alert(err.message);
                elBtnSendResetCode.disabled = false;
            }
        });
    }

    // Toggle Reset Password Visibility (Eye Icon)
    const elBtnToggleResetPassword = document.getElementById("btnToggleResetPassword");
    if (elBtnToggleResetPassword) {
        elBtnToggleResetPassword.addEventListener("click", () => {
            const type = elResetPasswordNew.getAttribute("type") === "password" ? "text" : "password";
            elResetPasswordNew.setAttribute("type", type);
            const eyeOpen = elBtnToggleResetPassword.querySelector(".eye-open");
            const eyeClosed = elBtnToggleResetPassword.querySelector(".eye-closed");
            if (type === "password") {
                if (eyeOpen) eyeOpen.style.display = "block";
                if (eyeClosed) eyeClosed.style.display = "none";
            } else {
                if (eyeOpen) eyeOpen.style.display = "none";
                if (eyeClosed) eyeClosed.style.display = "block";
            }
        });
    }

    // Reset Password Strength Meter
    const elResetPasswordStrengthWrapper = document.getElementById("resetPasswordStrengthWrapper");
    const elResetPasswordStrengthBar = document.getElementById("resetPasswordStrengthBar");
    const elResetPasswordStrengthText = document.getElementById("resetPasswordStrengthText");

    if (elResetPasswordNew) {
        elResetPasswordNew.addEventListener("input", () => {
            const val = elResetPasswordNew.value;
            if (!val) {
                elResetPasswordStrengthWrapper.style.display = "none";
                return;
            }
            elResetPasswordStrengthWrapper.style.display = "block";
            const strength = checkPasswordStrength(val);
            updateResetPasswordStrengthUI(strength);
        });
    }

    function updateResetPasswordStrengthUI(strength) {
        elResetPasswordStrengthText.textContent = strength;
        if (strength === "Weak") {
            elResetPasswordStrengthBar.style.width = "33%";
            elResetPasswordStrengthBar.style.backgroundColor = "var(--rose)";
            elResetPasswordStrengthText.style.color = "var(--rose)";
        } else if (strength === "Medium") {
            elResetPasswordStrengthBar.style.width = "66%";
            elResetPasswordStrengthBar.style.backgroundColor = "var(--amber)";
            elResetPasswordStrengthText.style.color = "var(--amber)";
        } else {
            elResetPasswordStrengthBar.style.width = "100%";
            elResetPasswordStrengthBar.style.backgroundColor = "var(--emerald)";
            elResetPasswordStrengthText.style.color = "var(--emerald)";
        }
    }

    // Reset Password Submission
    if (elFormResetPassword) {
        elFormResetPassword.addEventListener("submit", async (e) => {
            e.preventDefault();
            const username = elResetPasswordUsername.value.trim();
            const verification = elResetPasswordVerification.value.trim();
            const code = elResetPasswordCode.value.trim();
            const new_password = elResetPasswordNew.value;

            try {
                await apiRequest('/api/auth/reset-password', {
                    method: 'POST',
                    body: JSON.stringify({ username, verification, code, new_password })
                });
                alert("Password reset successfully! You can now log in with your new password.");
                closeModal(elModalResetPassword);
                clearResetTimer();

                // If user was logged in, log out to clear active session
                const status = await apiRequest('/api/auth/status');
                if (status.authenticated) {
                    await apiRequest('/api/auth/logout', { method: 'POST' });
                    state.problems = [];
                    state.plans = [];
                    state.user = { username: "Coder", is_admin: false, dailyTarget: 3 };
                    if (chartWeekly) chartWeekly.destroy();
                    if (chartTopic) chartTopic.destroy();
                    showAuthBackdrop();
                }
            } catch (err) {
                elResetPasswordErrorMsg.textContent = err.message;
                elResetPasswordErrorMsg.style.display = "block";
            }
        });
    }

    // Sidebar footer theme switcher
    elThemeToggle.addEventListener("click", () => {
        const curr = document.documentElement.getAttribute("data-theme") || 'dark';
        const next = curr === 'dark' ? 'light' : 'dark';
        applyTheme(next);
        renderCharts(); // Re-render charts to adjust text color
    });

    // Settings Modal
    document.getElementById("btnSettings").addEventListener("click", () => {
        document.getElementById("settingsUsername").value = state.user.username;
        document.getElementById("settingsDailyTarget").value = state.user.dailyTarget;
        openModal(elModalSettings);
    });
    document.getElementById("btnCloseSettingsModal").addEventListener("click", () => closeModal(elModalSettings));
    document.getElementById("btnCancelSettingsModal").addEventListener("click", () => closeModal(elModalSettings));

    // Save Settings Submit
    elFormSettings.addEventListener("submit", async (e) => {
        e.preventDefault();
        const username = document.getElementById("settingsUsername").value.trim();
        const daily_target = parseInt(document.getElementById("settingsDailyTarget").value, 10);
        
        try {
            await apiRequest('/api/user/settings', {
                method: 'POST',
                body: JSON.stringify({ username, daily_target })
            });
            closeModal(elModalSettings);
            await checkAuthStatus();
        } catch (err) {
            alert(err.message);
        }
    });

    // Danger Zone Data Reset
    elBtnResetProgress.addEventListener("click", async () => {
        const scope = elResetScope.value;
        let msg = "";
        if (scope === 'problems') msg = "Reset all solved problems count to 0? This will clear all problem history.";
        else if (scope === 'plans') msg = "Delete all personalized study plans? Problems will remain but be unlinked.";
        else msg = "Warning! Reset entire application data (problems, plans, user targets)? This cannot be undone.";

        if (confirm(msg)) {
            try {
                await apiRequest('/api/user/reset', {
                    method: 'POST',
                    body: JSON.stringify({ scope })
                });
                closeModal(elModalSettings);
                await fetchAllUserData();
            } catch (err) {
                alert(err.message);
            }
        }
    });

    // Log Problem triggers
    document.getElementById("btnLogProblemHeader").addEventListener("click", () => {
        elFormLogProblem.reset();
        elEditProblemId.value = "";
        elProblemDate.value = getTodayString();
        document.getElementById("modalLogTitle").textContent = "Log Solved Problem";
        openModal(elModalLogProblem);
    });
    
    document.getElementById("btnLogProblemEmpty")?.addEventListener("click", () => {
        elFormLogProblem.reset();
        elEditProblemId.value = "";
        elProblemDate.value = getTodayString();
        document.getElementById("modalLogTitle").textContent = "Log Solved Problem";
        openModal(elModalLogProblem);
    });

    document.getElementById("btnCloseLogModal").addEventListener("click", () => closeModal(elModalLogProblem));
    document.getElementById("btnCancelLogModal").addEventListener("click", () => closeModal(elModalLogProblem));

    // Log Problem Form Submit
    elFormLogProblem.addEventListener("submit", async (e) => {
        e.preventDefault();
        const pid = elEditProblemId.value || null;
        const name = elProblemName.value.trim();
        const difficulty = elProblemDifficulty.value;
        const platform = elProblemPlatform.value.trim();
        const topic = elProblemTopic.value.trim();
        const date = elProblemDate.value;
        const url = elProblemUrl.value.trim();
        const notes = elProblemNotes.value.trim();

        const checkedPlans = [];
        const checkboxes = elFormLogProblem.querySelectorAll("input[name='associatedPlans']:checked");
        checkboxes.forEach(cb => checkedPlans.push(cb.value));

        try {
            await apiRequest('/api/problems', {
                method: 'POST',
                body: JSON.stringify({
                    id: pid, name, difficulty, platform, topic, date, url, notes, plans: checkedPlans
                })
            });
            closeModal(elModalLogProblem);
            await fetchAllUserData();
        } catch (err) {
            alert(err.message);
        }
    });

    // Create Study Plan triggers
    document.getElementById("btnCreatePlan").addEventListener("click", () => {
        elFormCreatePlan.reset();
        openModal(elModalCreatePlan);
    });
    document.getElementById("btnClosePlanModal").addEventListener("click", () => closeModal(elModalCreatePlan));
    document.getElementById("btnCancelPlanModal").addEventListener("click", () => closeModal(elModalCreatePlan));

    // Create Study Plan Form Submit
    elFormCreatePlan.addEventListener("submit", async (e) => {
        e.preventDefault();
        const title = document.getElementById("planTitle").value.trim();
        const description = document.getElementById("planDescription").value.trim();
        const targetCount = parseInt(document.getElementById("planTargetCount").value, 10);
        const color = document.getElementById("planColor").value;

        try {
            await apiRequest('/api/plans', {
                method: 'POST',
                body: JSON.stringify({ title, description, targetCount, color })
            });
            closeModal(elModalCreatePlan);
            await fetchAllUserData();
        } catch (err) {
            alert(err.message);
        }
    });

    // Filters event listeners
    const triggerFilters = () => updateProblemsLogTable();
    elFilterSearch.addEventListener("input", triggerFilters);
    elFilterDifficulty.addEventListener("change", triggerFilters);
    elFilterPlatform.addEventListener("change", triggerFilters);
    elFilterTopic.addEventListener("change", triggerFilters);

    elBtnClearFilters.addEventListener("click", () => {
        elFilterSearch.value = "";
        elFilterDifficulty.value = "all";
        elFilterPlatform.value = "all";
        elFilterTopic.value = "all";
        updateProblemsLogTable();
    });

    // Distribution tab toggle buttons
    elBtnTabPlatforms.addEventListener("click", () => {
        elBtnTabPlatforms.classList.add("active");
        elBtnTabTopics.classList.remove("active");
        currentDistributionTab = "platforms";
        updatePerformanceDistribution();
    });

    elBtnTabTopics.addEventListener("click", () => {
        elBtnTabTopics.classList.add("active");
        elBtnTabPlatforms.classList.remove("active");
        currentDistributionTab = "topics";
        updatePerformanceDistribution();
    });

    // Select All Checkbox
    if (elSelectAllProblems) {
        elSelectAllProblems.addEventListener("change", () => {
            const isChecked = elSelectAllProblems.checked;
            const checkboxes = elProblemsTableBody.querySelectorAll(".problem-select-checkbox");
            checkboxes.forEach(cb => cb.checked = isChecked);
            updateBulkDeleteButtonState();
        });
    }

    // Bulk Delete Action Click
    if (elBtnBulkDelete) {
        elBtnBulkDelete.addEventListener("click", async () => {
            const checkedBoxes = elProblemsTableBody.querySelectorAll(".problem-select-checkbox:checked");
            const idsToDelete = Array.from(checkedBoxes).map(cb => cb.getAttribute("data-id"));
            
            if (idsToDelete.length === 0) return;
            
            if (confirm(`Are you sure you want to bulk delete the ${idsToDelete.length} selected problems?`)) {
                try {
                    await apiRequest('/api/problems/bulk-delete', {
                        method: 'POST',
                        body: JSON.stringify({ ids: idsToDelete })
                    });
                    await fetchAllUserData();
                } catch (err) {
                    alert(err.message);
                }
            }
        });
    }

    // Global ESC key to close modal
    window.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeModal(elModalLogProblem);
            closeModal(elModalCreatePlan);
            closeModal(elModalSettings);
            closeModal(elModalResetPassword);
        }
    });
}

function updateBulkDeleteButtonState() {
    const checkedBoxes = elProblemsTableBody.querySelectorAll(".problem-select-checkbox:checked");
    const count = checkedBoxes.length;
    
    if (count > 0) {
        elBtnBulkDelete.style.display = "inline-flex";
        elBulkDeleteCount.textContent = count;
    } else {
        elBtnBulkDelete.style.display = "none";
    }

    const allBoxes = elProblemsTableBody.querySelectorAll(".problem-select-checkbox");
    if (elSelectAllProblems && allBoxes.length > 0) {
        elSelectAllProblems.checked = (checkedBoxes.length === allBoxes.length);
    }
}
