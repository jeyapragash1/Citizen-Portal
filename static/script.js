// Utility to set active class for selected list item
function setActiveClass(selectedLi, listType) {
    let listSelector = '';
    if (listType === 'super-category-list') listSelector = '#super-category-list li';
    else if (listType === 'ministry-list') listSelector = '#ministry-list li';
    else if (listType === 'subservice-list') listSelector = '#subservice-list li';
    document.querySelectorAll(listSelector).forEach(li => li.classList.remove('active'));
    if (selectedLi) selectedLi.classList.add('active');
}
// Utility to get localized name from object or string
function getLocalizedName(nameObj, langParam) {
    // Prefer explicit langParam, otherwise use module-global `lang` variable, default to 'en'
    // Note: `lang` is a module-scoped variable (declared with let). Use it directly when available.
    const useLang = langParam || (typeof lang !== 'undefined' ? lang : 'en');
    if (!nameObj) return '';
    if (typeof nameObj === 'string') return nameObj;
    return nameObj[useLang] || nameObj['en'] || Object.values(nameObj)[0] || '';
}
// Utility to reset a panel's content and title
function resetPanel(panelUl, panelTitleEl, titleText, htmlContent) {
    if (panelTitleEl) panelTitleEl.textContent = titleText || '';
    if (panelUl) panelUl.innerHTML = '';
    if (htmlContent && panelUl) {
        let div = document.createElement('div');
        div.innerHTML = htmlContent;
        panelUl.appendChild(div);
    }
}
function renderSuperCategories() {
    console.debug('renderSuperCategories called, data length=', (allSuperCategoriesData || []).length);
    superCategoryListUl.innerHTML = '';
    if (!allSuperCategoriesData || allSuperCategoriesData.length === 0) {
        superCategoryListUl.innerHTML = '<li class="text-muted">No Super Categories found.</li>';
        return;
    }
    allSuperCategoriesData.forEach(sc => {
        console.debug('Rendering super category', sc.id, getLocalizedName(sc.name));
        let li = document.createElement('li');
        li.textContent = getLocalizedName(sc.name);
        li.dataset.superCategoryId = sc.id;
        li.onclick = () => {
            setActiveClass(li, 'super-category-list');
            loadMinistriesForSuperCategory(sc);
        };
        superCategoryListUl.appendChild(li);
    });
}
// --- Initial Data Load ---
async function loadInitialData() {
    try {
        const res = await fetch('/api/services');
        if (!res.ok) throw new Error('Failed to fetch services');
        allSuperCategoriesData = await res.json();
        renderSuperCategories();
    } catch (error) {
        console.error('Error loading initial data:', error);
        superCategoryListUl.innerHTML = '<li class="text-muted">Failed to load services.</li>';
    }
}
let lang = "en";
let allSuperCategoriesData = []; // Stores all hierarchical data (Super Categories -> Ministries -> Subservices)
let currentSelectedSuperCategory = null; // Stores the currently selected Super Category object
let currentSelectedMinistry = null;    // Stores the currently selected Ministry object
let currentSelectedSubservice = null;  // Stores the currently selected Subservice object
let currentQuestionData = null;        // Stores the currently clicked Question object
let currentSubserviceName = "";        // Stores the localized name of the selected subservice for engagement logging

let profile_id = null; // Stores the user's profile ID for progressive profiling

// --- DOM Element References ---
const superCategoryListUl = document.getElementById("super-category-list");
const ministryListUl = document.getElementById("ministry-list");
const subserviceListUl = document.getElementById("subservice-list");
const ministryPanelTitle = document.getElementById("ministry-panel-title");
const servicesQuestionsPanelTitle = document.getElementById("services-questions-panel-title");
const answerBoxDiv = document.getElementById("answer-box");

// AI Chat Modal elements
const askAiButton = document.getElementById('askAiButton');
const aiChatModalOverlay = document.getElementById('ai-chat-modal-overlay');
const closeChatBtn = document.querySelector('#ai-chat-modal-overlay .close-chat-btn');
const chatBody = document.getElementById('chat-body');
const chatTextInput = document.getElementById('chat-text-input');
const chatAutosuggestionsUl = document.getElementById('chat-autosuggestions');

// Progressive Profile Modal elements
let profileModalOverlay = null;
document.addEventListener('DOMContentLoaded', function() {
    profileModalOverlay = document.getElementById('profile-modal-overlay');
    // Move all event listeners and modal logic that use profileModalOverlay here
    // ...existing code...
});
const profileForm = document.getElementById('profile-form');
const profileStepTitle = document.getElementById('profile-step-title');
const closeProfileBtn = document.querySelector('#profile-modal-overlay .close-profile-btn');

// Global Search elements
const globalSearchInput = document.getElementById('global-search-input');
    resetPanel(subserviceListUl, servicesQuestionsPanelTitle, 'Select a Ministry to view Services/Questions', `
        <h3>Welcome to Citizen Services Portal!</h3>
        <p>Use the search bar above or select a Super Category, then a Ministry, and finally a Service to find information.</p>
        <p class="text-muted">Your interactions help us improve services for everyone. Click "Ask AI" in the header to use our AI assistant!</p>
    `);

function setLang(newLang) {
    lang = newLang;
    // Update document language attribute
    try { document.documentElement.lang = newLang; } catch (e) {}

    // Update active state on language buttons (if present)
    const enBtn = document.getElementById('lang-en-btn');
    const siBtn = document.getElementById('lang-si-btn');
    const taBtn = document.getElementById('lang-ta-btn');
    if (enBtn) enBtn.classList.toggle('active', newLang === 'en');
    if (siBtn) siBtn.classList.toggle('active', newLang === 'si');
    if (taBtn) taBtn.classList.toggle('active', newLang === 'ta');

    // Re-render visible panels with the new language
    renderSuperCategories(); // left panel
    if (currentSelectedSuperCategory) {
        loadMinistriesForSuperCategory(currentSelectedSuperCategory, currentSelectedMinistry);
    }
    if (currentSelectedMinistry) {
        loadSubservicesForMinistry(currentSelectedMinistry, currentSelectedSubservice);
    }
    if (currentQuestionData) {
        showAnswer(currentQuestionData);
    }
    // Re-load ads so localized titles/bodies update
    try { loadAds(); } catch (e) {}
}

function loadMinistriesForSuperCategory(superCategory, ministryToActivate = null) {
    currentSelectedSuperCategory = superCategory;
    currentSelectedMinistry = null;
    currentSelectedSubservice = null;
    currentQuestionData = null;

    resetPanel(ministryListUl, ministryPanelTitle, `${getLocalizedName(superCategory.name)}: Ministries`);
    resetPanel(subserviceListUl, servicesQuestionsPanelTitle, 'Select a Ministry to view Services/Questions', `
        <h3>Select a Ministry to view services.</h3>
        <p class="text-muted">Explore the departments under ${getLocalizedName(superCategory.name)}.</p>
    `);

    (superCategory.ministries || []).forEach(ministry => {
        let li = document.createElement("li");
        li.textContent = getLocalizedName(ministry.name);
        li.dataset.ministryId = ministry.id;
        li.dataset.superCategoryId = superCategory.id;
        li.onclick = () => {
            currentSelectedMinistry = ministry;
            setActiveClass(li, 'ministry-list');
            loadSubservicesForMinistry(ministry);
        };
        ministryListUl.appendChild(li);
    });
// Show compulsory profile modal for Ministry selection
function showProfileModalForMinistry(ministry) {
    profileModalOverlay.style.display = 'flex';
    profileForm.reset();
    document.getElementById('profile-step-1').style.display = 'block';
    document.getElementById('profile-step-2').style.display = 'none';
    document.getElementById('profile-step-3').style.display = 'none';
    profileStepTitle.textContent = `Please fill out this form to continue`;
    // After submit, show subservices/questions for selected ministry
    profileForm.onsubmit = async (e) => {
        e.preventDefault();
        await profileSubmit();
        closeProfileModal();
        loadSubservicesForMinistry(ministry);
    };
}

    if (ministryToActivate) {
        const activeMinistryLi = ministryListUl.querySelector(`[data-ministry-id="${ministryToActivate.id}"]`);
        if (activeMinistryLi) {
            setActiveClass(activeMinistryLi, 'ministry-list');
            loadSubservicesForMinistry(ministryToActivate, subserviceToActivate); // Pass subserviceToActivate
        }
    }
}

function loadSubservicesForMinistry(ministry, subserviceToActivate = null) {
    currentSelectedMinistry = ministry;
    currentSelectedSubservice = null;
    currentQuestionData = null;

    resetPanel(subserviceListUl, servicesQuestionsPanelTitle, `${getLocalizedName(ministry.name)}: Services & Questions`);
    answerBoxDiv.innerHTML = `
        <h3>Select a service to view questions.</h3>
        <p class="text-muted">Find specific services and answers from ${getLocalizedName(ministry.name)}.</p>
    `;

    (ministry.subservices || []).forEach(subservice => {
        let li = document.createElement("li");
        li.innerHTML = `<b>${getLocalizedName(subservice.name)}</b> <i class="fas fa-chevron-down" style="float:right;"></i>`;
        li.dataset.subserviceId = subservice.id;
        li.dataset.ministryId = ministry.id;
        li.classList.add('subservice-item-toggle');

            // When user clicks a subservice, show compulsory question form (profile modal)
            li.addEventListener('click', function(e) {
                e.stopPropagation();
                currentSelectedSubservice = subservice;
                // Debug log to confirm modal logic is running
                console.log('Modal logic triggered for service:', getLocalizedName(subservice.name));
                profileModalOverlay.classList.add('active');
                profileModalOverlay.style.display = 'flex';
                console.log('Modal overlay classes:', profileModalOverlay.className);
                profileForm.reset();
                profileStepTitle.textContent = `Please fill out this form to continue`;
                profileForm.onsubmit = async (ev) => {
                    ev.preventDefault();
                    // Validate all fields as compulsory
                    const name = document.getElementById('p_name').value.trim();
                    const age = document.getElementById('p_age').value.trim();
                    const email = document.getElementById('p_email').value.trim();
                    const phone = document.getElementById('p_phone').value.trim();
                    const job = document.getElementById('p_job').value.trim();
                    const desire = document.getElementById('p_desire').value.trim();
                    if (!name || !age || !email || !phone || !job || !desire) {
                        alert("All fields are required. Please fill out every detail.");
                        return;
                    }
                    await profileSubmit();
                    closeProfileModal();
                    showQuestionsForSubservice(subservice);
                };
            });

        subserviceListUl.appendChild(li);
    });
// Show compulsory profile modal for Subservice selection
function showProfileModalForSubservice(subservice) {
    profileModalOverlay.style.display = 'flex';
    profileForm.reset();
    profileStepTitle.textContent = `Please fill out this form to continue`;
    // After submit, show service questions/answers for selected subservice
    profileForm.onsubmit = async (e) => {
        e.preventDefault();
        await profileSubmit();
        closeProfileModal();
        showQuestionsForSubservice(subservice);
    };
}

function showQuestionsForSubservice(subservice) {
    // Render the questions for the selected subservice
    resetPanel(subserviceListUl, servicesQuestionsPanelTitle, `${getLocalizedName(subservice.name)}: Questions`);
    answerBoxDiv.innerHTML = `<h3>Select a question to view the answer.</h3>`;
    let questionsUl = document.createElement("ul");
    questionsUl.classList.add('question-list');
    (subservice.questions || []).forEach(q => {
        let qLi = document.createElement("li");
        qLi.textContent = getLocalizedName(q.q);
        qLi.dataset.questionText = getLocalizedName(q.q);
        qLi.classList.add('question-item');
        qLi.onclick = (e) => {
            e.stopPropagation();
            currentQuestionData = q;
            currentSubserviceName = getLocalizedName(subservice.name);
            showAnswer(q);
        };
        questionsUl.appendChild(qLi);
    });
    subserviceListUl.appendChild(questionsUl);
}

    if (subserviceToActivate) {
        const activeSubserviceLi = subserviceListUl.querySelector(`[data-subservice-id="${subserviceToActivate.id}"]`);
        if (activeSubserviceLi) {
            activeSubserviceLi.click(); // Simulate click to expand and activate
            currentSelectedSubservice = subserviceToActivate; // Ensure this is set for "More Details"
        }
    }
}

function showAnswer(q) {
    let html = `<h3>${getLocalizedName(q.q)}</h3>`;
    html += `<p>${getLocalizedName(q.answer)}</p>`;
    
    const downloadIcon = `<i class="fas fa-download"></i>`;
    const locationIcon = `<i class="fas fa-map-marker-alt"></i>`;
    const instructionsIcon = `<i class="fas fa-info-circle"></i>`;

    if (q.downloads && q.downloads.length) {
        html += `<p><b>${downloadIcon} Downloads:</b> ${q.downloads.map(d=>`<a href="${d}" target="_blank">${d.split("/").pop()}</a>`).join(", ")}</p>`;
    }
    if (q.location) {
        html += `<p><b>${locationIcon} Location:</b> <a href="${q.location}" target="_blank">View Map</a></p>`;
    }
    if (q.instructions) {
        html += `<p><b>${instructionsIcon} Instructions:</b> ${q.instructions}</p>`;
    }

    answerBoxDiv.innerHTML = html;

    // Add "More Details" for the current subservice
    if (currentSelectedSubservice && currentSelectedMinistry) {
        const moreDetailsHtml = `
            <div class="subservice-details-box">
                <h4>You've inquired about: ${getLocalizedName(currentSelectedSubservice.name)}</h4>
                <p>Click below to see all services and questions under this department.</p>
                <a href="/ministry/${currentSelectedMinistry.id}" class="view-all-btn">
                    <i class="fas fa-list"></i> View All Services for ${getLocalizedName(currentSelectedMinistry.name)}
                </a>
            </div>
        `;
        answerBoxDiv.insertAdjacentHTML('beforeend', moreDetailsHtml);
    }

    // Log engagement without prompting (profile data collected via profile modal)
    fetch("/api/engagement", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({
            user_id: profile_id, // Use gathered profile_id
            age: null, // Age is in profile, not directly logged with answer anymore
            job: null, // Job is in profile
            desires: [], // Desires in profile
            question_clicked: getLocalizedName(q.q),
            service: currentSubserviceName,
            source: "direct_click"
        })
    });
}

function viewAllServicesForCurrentMinistry() {
    if (!currentSelectedMinistry) {
        alert("Error: No ministry currently selected.");
        return;
    }
    loadSubservicesForMinistry(currentSelectedMinistry, currentSelectedSubservice);

    const ministryLi = ministryListUl.querySelector(`[data-ministry-id="${currentSelectedMinistry.id}"]`);
    if (ministryLi) {
        setActiveClass(ministryLi, 'ministry-list');
    }
}


// --- AI Chat Modal Functions ---
askAiButton?.addEventListener('click', openAIChatModal);

function openAIChatModal() {
    aiChatModalOverlay.style.display = 'flex';
    chatTextInput.focus();
}

closeChatBtn?.addEventListener('click', closeAIChatModal);

function closeAIChatModal() {
    aiChatModalOverlay.style.display = 'none';
    chatTextInput.value = ''; // Clear input
    chatAutosuggestionsUl.innerHTML = ''; // Clear suggestions
}

chatTextInput.addEventListener('input', () => chatAutosuggest(chatTextInput.value));
chatTextInput.addEventListener('keyup', (e) => {
    if (e.key === 'Enter') {
        sendAIChat();
    }
});

async function sendAIChat() {
    const text = chatTextInput.value.trim();
    if (!text) return;

    appendChatMessage("user", text);
    chatTextInput.value = ""; // Clear input after sending
    chatAutosuggestionsUl.innerHTML = ''; // Clear autosuggestions

    // Call AI endpoint
    try {
        const res = await fetch("/api/ai/search", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body: JSON.stringify({query: text, top_k: 5})
        });
        const data = await res.json();
        let reply = data.answer || "I'm sorry, I couldn't find an answer to that. Please try rephrasing your question.";
        appendChatMessage("bot", reply);

        // Log engagement for AI chat query
        fetch("/api/engagement", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body: JSON.stringify({user_id: profile_id, question_clicked: text, service: null, source: "ai_chat"})
        });

    } catch (error) {
        console.error("Error with AI search:", error);
        appendChatMessage("bot", "Oops! Something went wrong with the AI assistant. Please try again later.");
    }
}

function appendChatMessage(sender, text){
    const div = document.createElement("div");
    div.className = `chat-msg ${sender}-msg`;
    div.innerText = text;
    chatBody.appendChild(div);
    chatBody.scrollTop = chatBody.scrollHeight; // Scroll to bottom
}

// --- Chat Autosuggest (can reuse global search logic, but for chat input) ---
let chatSuggestTimeout = null;
async function chatAutosuggest(q){
    clearTimeout(chatSuggestTimeout);
    chatAutosuggestionsUl.innerHTML = ""; // Clear existing suggestions

    if(!q || q.length < 2){
        return;
    }

    chatSuggestTimeout = setTimeout(async ()=>{
        // Reusing the general autosuggest logic by calling a helper
        const items = await fetchSearchResults(q); // Call a helper that fetches from /api/search/autosuggest
        
        if (items.length > 0) {
            items.forEach(item => {
                let li = document.createElement('li');
                li.innerHTML = `${getLocalizedName(item.name)} <span class="text-muted category">(${getLocalizedName(item.super_category_name)})</span>`;
                li.onclick = () => {
                    chatTextInput.value = getLocalizedName(item.name); // Fill input with suggestion
                    chatAutosuggestionsUl.innerHTML = ''; // Clear suggestions
                    // Optionally, trigger sendAIChat immediately or allow user to press Enter
                };
                chatAutosuggestionsUl.appendChild(li);
            });
            chatAutosuggestionsUl.classList.add('active'); // Add active class to show it
        } else {
            chatAutosuggestionsUl.classList.remove('active');
        }
    }, 250);
}


// --- Progressive Profile Modal Functions ---
function showProfileModal() {
    profileModalOverlay.style.display = 'flex';
    profileForm.reset(); // Clear form fields
    // Ensure step 1 is visible, others hidden
    document.getElementById('profile-step-1').style.display = 'block';
    document.getElementById('profile-step-2').style.display = 'none';
    document.getElementById('profile-step-3').style.display = 'none';
    profileStepTitle.textContent = "Tell us about you";
}

closeProfileBtn?.addEventListener('click', closeProfileModal);

function closeProfileModal() {
    // Always re-get the modal overlay in case DOM changed
    const modalEl = document.getElementById('profile-modal-overlay');
    if (!modalEl) {
        console.warn('closeProfileModal: profile-modal-overlay not found');
        return;
    }
    if (modalEl.style) {
        modalEl.classList.remove('active');
        modalEl.style.display = 'none';
    }
    if (typeof profileForm !== 'undefined' && profileForm) {
        profileForm.reset();
        profileForm.onsubmit = null;
    }
    const step1 = document.getElementById('profile-step-1');
    const step2 = document.getElementById('profile-step-2');
    const step3 = document.getElementById('profile-step-3');
    if (step1) step1.style.display = 'block';
    if (step2) step2.style.display = 'none';
    if (step3) step3.style.display = 'none';
}

function profileNext(currentStep) {
    // Basic validation for current step fields
    let isValid = true;
    if (currentStep === 1) {
        const name = document.getElementById('p_name').value.trim();
        const age = document.getElementById('p_age').value.trim();
        if (!name || !age) {
            alert("Name and Age are required.");
            isValid = false;
        }
    } else if (currentStep === 2) {
        // Email/phone are optional for step 2, no mandatory validation here
    }
    // No validation for step 3 here, as submit handles it

    if (isValid) {
        document.getElementById(`profile-step-${currentStep}`).style.display = 'none';
        document.getElementById(`profile-step-${currentStep + 1}`).style.display = 'block';
        profileStepTitle.textContent = `Tell us about you (Step ${currentStep + 1} of 3)`;
    }
}

function profileBack(currentStep) {
    document.getElementById(`profile-step-${currentStep}`).style.display = 'none';
    document.getElementById(`profile-step-${currentStep - 1}`).style.display = 'block';
    profileStepTitle.textContent = `Tell us about you (Step ${currentStep - 1} of 3)`;
}

profileForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    profileSubmit(); // Call the async submit function
});

async function profileSubmit() {
    const name = document.getElementById('p_name').value.trim();
    const age = document.getElementById('p_age').value.trim();
    const email = document.getElementById('p_email').value.trim();
    const phone = document.getElementById('p_phone').value.trim();
    const job = document.getElementById('p_job').value.trim();
    const desire = document.getElementById('p_desire').value.trim();

    // All fields are compulsory
    const profileData = {
        name,
        age,
        email,
        phone,
        job,
        desires: [desire]
    };

    try {
        // Send all data in one step
        let res = await fetch("/api/profile/step", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({step: "all", data: profileData})
        });
        let j = await res.json();
        profile_id = j.profile_id || null;

        // After successful profile submission, display the answer for the original question
        if (currentQuestionData) {
            showAnswer(currentQuestionData);
        } else {
            answerBoxDiv.innerHTML = `<h3>Profile Completed!</h3><p>Thank you for providing your details. Please select a question to view its answer.</p>`;
        }
        closeProfileModal();

    } catch (error) {
        console.error("Error submitting profile:", error);
        alert("Failed to save your profile. Please try again.");
    }
}


// --- Global Search Functionality ---
let globalSearchTimeout = null;

globalSearchInput.addEventListener('input', (e) => {
    clearTimeout(globalSearchTimeout);
    const query = e.target.value.toLowerCase().trim();

    if (query.length < 2) {
        searchResultsUl.classList.remove('active');
        searchResultsUl.innerHTML = '';
        return;
    }

    globalSearchTimeout = setTimeout(async () => {
        const items = await fetchSearchResults(query); // Use helper function
        renderSearchResults(items);
    }, 300);
});

globalSearchInput.addEventListener('focus', () => {
    if (globalSearchInput.value.length >= 2 && searchResultsUl.children.length > 0) {
        searchResultsUl.classList.add('active');
    }
});

globalSearchInput.addEventListener('blur', (e) => {
    if (!e.relatedTarget || !e.relatedTarget.closest('#search-results')) {
        setTimeout(() => {
            searchResultsUl.classList.remove('active');
        }, 150);
    }
});

async function fetchSearchResults(query) {
    try {
        const res = await fetch(`/api/search/autosuggest?q=${encodeURIComponent(query)}`);
        if (!res.ok) throw new Error('Network response was not ok.');
        return await res.json();
    } catch (error) {
        console.error("Failed to fetch search results:", error);
        return [];
    }
}

function renderSearchResults(matchedItems) {
    searchResultsUl.innerHTML = '';
    if (matchedItems.length > 0) {
        matchedItems.forEach(match => {
            let li = document.createElement('li');
            li.innerHTML = `${getLocalizedName(match.name)} <span class="text-muted category">(${getLocalizedName(match.super_category_name || match.ministry_name)})</span>`;
            li.onclick = () => handleSearchResultClick(match);
            searchResultsUl.appendChild(li);
        });
        searchResultsUl.classList.add('active');
    } else {
        let li = document.createElement('li');
        li.textContent = "No matching services or questions found.";
        searchResultsUl.appendChild(li);
        searchResultsUl.classList.add('active');
    }
}

function handleSearchResultClick(match) {
    setActiveClass(null, 'super-category-list');
    setActiveClass(null, 'ministry-list');
    
    if (match.type === 'ministry') {
        const superCategory = allSuperCategoriesData.find(sc => sc.id === match.super_category_id);
        if (superCategory) {
            loadMinistriesForSuperCategory(superCategory, match.ministry);
            const superCatLi = superCategoryListUl.querySelector(`[data-super-category-id="${superCategory.id}"]`);
            if (superCatLi) setActiveClass(superCatLi, 'super-category-list');
        }
    } else if (match.type === 'subservice') {
        const superCategory = allSuperCategoriesData.find(sc => sc.id === match.super_category_id);
        const ministry = superCategory?.ministries.find(min => min.id === match.ministry_id);
        if (superCategory && ministry) {
            loadMinistriesForSuperCategory(superCategory, ministry);
            const superCatLi = superCategoryListUl.querySelector(`[data-super-category-id="${superCategory.id}"]`);
            if (superCatLi) setActiveClass(superCatLi, 'super-category-list');
            setTimeout(() => {
                loadSubservicesForMinistry(ministry, match.subservice);
                const ministryLi = ministryListUl.querySelector(`[data-ministry-id="${ministry.id}"]`);
                if (ministryLi) setActiveClass(ministryLi, 'ministry-list');
            }, 50);
        }
    } else if (match.type === 'question') {
        const superCategory = allSuperCategoriesData.find(sc => sc.id === match.super_category_id);
        const ministry = superCategory?.ministries.find(min => min.id === match.ministry_id);
        const subservice = ministry?.subservices.find(sub => sub.id === match.subservice_id);
        const question = subservice?.questions.find(q => getLocalizedName(q.q) === getLocalizedName(match.question.q)); // Match by text or ID if available
        
        if (superCategory && ministry && subservice && question) {
            loadMinistriesForSuperCategory(superCategory, ministry);
            const superCatLi = superCategoryListUl.querySelector(`[data-super-category-id="${superCategory.id}"]`);
            if (superCatLi) setActiveClass(superCatLi, 'super-category-list');
            setTimeout(() => {
                loadSubservicesForMinistry(ministry, subservice);
                const ministryLi = ministryListUl.querySelector(`[data-ministry-id="${ministry.id}"]`);
                if (ministryLi) setActiveClass(ministryLi, 'ministry-list');
                setTimeout(() => {
                    currentSelectedSubservice = subservice;
                    currentQuestionData = question;
                    currentSubserviceName = getLocalizedName(subservice.name);
                    showProfileModal(); // Trigger profile modal for question
                }, 100);
            }, 50);
        }
    }
    globalSearchInput.value = '';
    searchResultsUl.classList.remove('active');
}


// --- Ads Loading ---
async function loadAds(){
    try {
        const res = await fetch("/api/ads");
        const ads = await res.json();
        adsAreaDiv.innerHTML = `<h3>Announcements</h3>`; // Clear existing "Loading ads..."
        if (ads.length > 0) {
            ads.forEach(a => {
                const adHtml = `
                    <div class="ad-card">
                        <a href="${a.link || '#'}" target="_blank" onclick="logAdClick('${a.id}')">
                            <h4>${getLocalizedName(a.title)}</h4>
                            <p>${getLocalizedName(a.body)}</p>
                        </a>
                    </div>
                `;
                adsAreaDiv.insertAdjacentHTML('beforeend', adHtml);
            });
        } else {
            adsAreaDiv.insertAdjacentHTML('beforeend', '<p class="text-muted text-center">No announcements available.</p>');
        }
    } catch (error) {
        console.error("Failed to load ads:", error);
        adsAreaDiv.innerHTML = `<h3>Announcements</h3><p class="text-muted text-center">Failed to load announcements.</p>`;
    }
}

function logAdClick(adId) {
    fetch("/api/engagement", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({user_id: profile_id, ad: adId, source: "ad_click"})
    });
}


// --- Initial Load ---
window.onload = loadInitialData;

// --- Floating Chatbot UI Logic (separate from service page) ---
document.addEventListener('DOMContentLoaded', function() {
    const floatingBtn = document.getElementById('floating-chatbot-btn');
    const chatbotModal = document.getElementById('chatbot-modal');
    const closeBtn = document.getElementById('close-chatbot-modal');
    const messagesDiv = document.getElementById('chatbot-messages');
    const input = document.getElementById('chatbot-input');
    const sendBtn = document.getElementById('chatbot-send-btn');

    // Open modal
    if (floatingBtn) {
        floatingBtn.addEventListener('click', function() {
            chatbotModal.style.display = 'flex';
            input.focus();
            if (messagesDiv.childElementCount === 0) {
                appendChatbotMessage('bot', "Hi! I'm your virtual assistant. How can I help you?", new Date());
            }
        });
    }
    // Close modal
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            chatbotModal.style.display = 'none';
            input.value = '';
        });
    }
    // Send message
    if (sendBtn) {
        if (!date) return '';
        const d = new Date(date);
        return d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
    }
});

// --- Floating Chatbot UI Logic ---
document.addEventListener('DOMContentLoaded', function() {
    const floatingBtn = document.getElementById('floating-chatbot-btn');
    const chatbotModal = document.getElementById('chatbot-modal');
    const closeBtn = document.getElementById('close-chatbot-modal');
    const messagesDiv = document.getElementById('chatbot-messages');
    const input = document.getElementById('chatbot-input');
    const sendBtn = document.getElementById('chatbot-send-btn');

    // Open modal
    if (floatingBtn) {
        floatingBtn.addEventListener('click', function() {
            chatbotModal.style.display = 'block';
            input.focus();
            if (messagesDiv.childElementCount === 0) {
                appendChatbotMessage('bot', "Hi! I'm your virtual assistant. How can I help you?", new Date());
            }
        });
    }
    // Close modal
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            chatbotModal.style.display = 'none';
            input.value = '';
        });
    }
    // Send message
    if (sendBtn) {
        sendBtn.addEventListener('click', sendChatbotMessage);
    }
    if (input) {
        input.addEventListener('keyup', function(e) {
            if (e.key === 'Enter') sendChatbotMessage();
        });
    }

    async function sendChatbotMessage() {
        const text = input.value.trim();
        if (!text) return;
        appendChatbotMessage('user', text, new Date());
        input.value = '';
        try {
            const res = await fetch("/api/ai/search", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({query: text, top_k: 5})
            });
            const data = await res.json();
            let reply = data.answer || "I'm sorry, I couldn't find an answer to that. Please try rephrasing your question.";
            appendChatbotMessage('bot', reply, new Date());
        } catch (error) {
            appendChatbotMessage('bot', "Oops! Something went wrong with the AI assistant. Please try again later.", new Date());
        }
    }

    function appendChatbotMessage(sender, text, timestamp) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `chatbot-message ${sender}`;
        // Avatar
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'chatbot-avatar';
        if (sender === 'bot') {
            avatarDiv.innerHTML = '<i class="fas fa-robot"></i>';
        } else {
            avatarDiv.innerHTML = '<i class="fas fa-user"></i>';
        }
        // Bubble
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'chatbot-bubble';
        bubbleDiv.innerText = text;
        // Timestamp
        const tsDiv = document.createElement('div');
        tsDiv.className = 'chatbot-timestamp';
        tsDiv.innerText = formatTimestamp(timestamp);
        // Layout
        if (sender === 'bot') {
            msgDiv.appendChild(avatarDiv);
            msgDiv.appendChild(bubbleDiv);
        } else {
            msgDiv.appendChild(bubbleDiv);
            msgDiv.appendChild(avatarDiv);
        }
        msgDiv.appendChild(tsDiv);
        messagesDiv.appendChild(msgDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    function formatTimestamp(date) {
        if (!date) return '';
        const d = new Date(date);
        return d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
    }
});