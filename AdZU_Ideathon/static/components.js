/**
 * ZCMC Regional Health Exchange: Reusable UI Components & Cryptographic Vault Engine
 * Provides standard Sidebar (Desktop), App Header (Mobile), Bottom Navigation (Mobile),
 * Network Simulation, and Client-Side Web Crypto AES-256 Store-and-Forward Vault.
 */

(function (window) {
    const VAULT_STORAGE_KEY = "zcmc_secure_vault_records_v1";
    const DEVICE_SECRET_SEED = "ZCMC-ZAMBASULTA-EDGE-KEY-2026-CHDIX";

    let isHardwareOnline = navigator.onLine;
    let isSimulatedOnline = true;
    let syncListeners = [];

    // Web Crypto API Key derivation
    async function getDerivedCryptoKey() {
        const enc = new TextEncoder();
        const keyMaterial = await window.crypto.subtle.importKey(
            "raw",
            enc.encode(DEVICE_SECRET_SEED),
            { name: "PBKDF2" },
            false,
            ["deriveKey"]
        );
        return window.crypto.subtle.deriveKey(
            {
                name: "PBKDF2",
                salt: enc.encode("ZCMC_RURAL_GIDA_SALT_2026"),
                iterations: 100000,
                hash: "SHA-256"
            },
            keyMaterial,
            { name: "AES-GCM", length: 256 },
            false,
            ["encrypt", "decrypt"]
        );
    }

    async function encryptPayload(dataObj) {
        const key = await getDerivedCryptoKey();
        const enc = new TextEncoder();
        const iv = window.crypto.getRandomValues(new Uint8Array(12));
        const plaintextBytes = enc.encode(JSON.stringify(dataObj));

        const ciphertextBuffer = await window.crypto.subtle.encrypt(
            { name: "AES-GCM", iv: iv },
            key,
            plaintextBytes
        );

        let binary = '';
        const bytes = new Uint8Array(ciphertextBuffer);
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        const b64Ciphertext = btoa(binary);

        let ivBinary = '';
        for (let i = 0; i < iv.byteLength; i++) {
            ivBinary += String.fromCharCode(iv[i]);
        }
        const b64Iv = btoa(ivBinary);

        return {
            id: dataObj.id,
            origin_facility: dataObj.origin_facility,
            urgency: dataObj.urgency,
            ciphertext: b64Ciphertext,
            iv: b64Iv,
            is_encrypted: true,
            masked_patient: "AES-256 [Patient PII Sealed]",
            primary_diagnosis: "Encrypted Clinical Record",
            transit_status: dataObj.transit_status || "pending_transit",
            timestamp: Date.now()
        };
    }

    async function decryptPayload(envelope) {
        if (!envelope.ciphertext || !envelope.iv) return envelope;
        const key = await getDerivedCryptoKey();
        const ciphertextBytes = Uint8Array.from(atob(envelope.ciphertext), c => c.charCodeAt(0));
        const ivBytes = Uint8Array.from(atob(envelope.iv), c => c.charCodeAt(0));

        const decryptedBuffer = await window.crypto.subtle.decrypt(
            { name: "AES-GCM", iv: ivBytes },
            key,
            ciphertextBytes
        );

        const dec = new TextDecoder();
        return JSON.parse(dec.decode(decryptedBuffer));
    }

    function getEncryptedVault() {
        try {
            const raw = localStorage.getItem(VAULT_STORAGE_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            console.error("Failed to load vault:", e);
            return [];
        }
    }

    function saveEncryptedVault(records) {
        try {
            localStorage.setItem(VAULT_STORAGE_KEY, JSON.stringify(records));
            updateAllBadges();
        } catch (e) {
            console.error("Failed to save vault:", e);
        }
    }

    function isEffectiveOnline() {
        return isHardwareOnline && isSimulatedOnline;
    }

    function setSimulatedNetwork(isOnline) {
        isSimulatedOnline = isOnline;
        const simOnBtns = document.querySelectorAll(".sim-online-btn");
        const simOffBtns = document.querySelectorAll(".sim-offline-btn");
        const notice = document.getElementById("zcmcOfflineNotice");

        if (isOnline) {
            simOnBtns.forEach(b => {
                b.className = "sim-online-btn px-2.5 py-1 rounded text-xs font-bold bg-emerald-600 text-white shadow-xs transition";
            });
            simOffBtns.forEach(b => {
                b.className = "sim-offline-btn px-2.5 py-1 rounded text-xs font-bold text-slate-300 hover:bg-slate-800 transition";
            });
            if (notice) notice.classList.add("hidden");
            showToast("Connected to Central ZCMC Hub.", "success");
            flushOfflineQueue();
        } else {
            simOnBtns.forEach(b => {
                b.className = "sim-online-btn px-2.5 py-1 rounded text-xs font-bold text-slate-300 hover:bg-slate-800 transition";
            });
            simOffBtns.forEach(b => {
                b.className = "sim-offline-btn px-2.5 py-1 rounded text-xs font-bold bg-rose-700 text-white shadow-xs transition";
            });
            if (notice) notice.classList.remove("hidden");
            showToast("Island Outage simulated. Store-and-forward AES-256 active.", "error");
        }
        updateOnlineStatusUI();
    }

    function updateOnlineStatusUI() {
        const badges = document.querySelectorAll(".zcmc-connection-badge");
        const dots = document.querySelectorAll(".zcmc-conn-dot");
        const texts = document.querySelectorAll(".zcmc-conn-text");

        const online = isEffectiveOnline();
        badges.forEach(b => {
            b.className = online 
                ? "zcmc-connection-badge flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-950/80 border border-zcmc-mint/40 text-zcmc-mint touch-action"
                : "zcmc-connection-badge flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-rose-950/80 border border-rose-500/50 text-rose-300 touch-action";
        });
        dots.forEach(d => {
            d.className = online 
                ? "zcmc-conn-dot w-2 h-2 rounded-full bg-emerald-400 animate-pulse"
                : "zcmc-conn-dot w-2 h-2 rounded-full bg-rose-400";
        });
        texts.forEach(t => {
            t.innerText = online ? "Online Link" : "Island Outage";
        });
    }

    function updateAllBadges() {
        const vault = getEncryptedVault();
        const count = vault.length;
        document.querySelectorAll(".zcmc-vault-count").forEach(el => {
            el.innerText = count;
        });

        const dots = document.querySelectorAll(".zcmc-vault-indicator-dot");
        dots.forEach(d => {
            if (count > 0) d.classList.remove("hidden");
            else d.classList.add("hidden");
        });
    }

    function showToast(message, type = 'success') {
        let container = document.getElementById("zcmcToastContainer");
        if (!container) {
            container = document.createElement("div");
            container.id = "zcmcToastContainer";
            container.className = "fixed top-3 left-4 right-4 z-50 flex flex-col gap-2 max-w-md mx-auto pointer-events-none";
            document.body.appendChild(container);
        }

        const toast = document.createElement("div");
        const bgClass = type === 'success' ? 'bg-zcmc-forest text-white border-zcmc-gold' : 'bg-rose-900 text-white border-rose-400';
        toast.className = `${bgClass} border px-3.5 py-2.5 rounded-xl shadow-xl text-xs font-medium flex items-center justify-between gap-3 pointer-events-auto transition transform duration-200 translate-y-1 opacity-0`;
        toast.innerHTML = `<span>${message}</span><button onclick="this.parentElement.remove()" class="text-white/70 hover:text-white">&times;</button>`;
        container.appendChild(toast);

        setTimeout(() => toast.classList.remove('translate-y-1', 'opacity-0'), 10);
        setTimeout(() => {
            toast.classList.add('opacity-0');
            setTimeout(() => toast.remove(), 250);
        }, 3500);
    }

    async function flushOfflineQueue() {
        if (!isEffectiveOnline()) {
            showToast("Network is offline. Reconnect to forward records.", "error");
            return;
        }

        const vault = getEncryptedVault();
        if (vault.length === 0) {
            showToast("Device Vault is clear. All records synced.", "success");
            return;
        }

        try {
            const decryptedRecords = [];
            for (const envelope of vault) {
                const clear = await decryptPayload(envelope);
                decryptedRecords.push(clear);
            }

            const res = await fetch("/api/sync/push", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ client_id: "edge-terminal", records: decryptedRecords })
            });

            if (res.ok) {
                const result = await res.json();
                saveEncryptedVault([]);
                showToast(`Forwarded ${result.synced_count} records from vault to ZCMC Hub.`, "success");
                syncListeners.forEach(fn => fn());
                closeVaultModal();
            }
        } catch (err) {
            console.error("Flush failed:", err);
            showToast("Failed to connect to central hub.", "error");
        }
    }

    function openVaultModal() {
        const modal = document.getElementById("zcmcVaultModal");
        if (!modal) return;
        const vault = getEncryptedVault();
        const container = document.getElementById("zcmcVaultModalContent");

        container.innerHTML = "";
        if (vault.length === 0) {
            container.innerHTML = `
                <div class="p-8 text-center bg-white border border-dashed border-slate-300 rounded-xl">
                    <svg class="w-10 h-10 mx-auto text-emerald-600 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/>
                    </svg>
                    <p class="text-xs font-bold text-slate-800">Local Outbox Vault Clear</p>
                    <p class="text-[11px] text-slate-500 mt-1">All offline patient referrals have been securely forwarded to ZCMC Hub.</p>
                </div>
            `;
        } else {
            vault.forEach((env) => {
                const card = document.createElement("div");
                card.className = "bg-white p-3.5 rounded-xl border border-slate-300 shadow-xs space-y-2 text-xs";
                card.innerHTML = `
                    <div class="flex items-center justify-between border-b border-slate-100 pb-2">
                        <div class="flex items-center gap-1.5">
                            <span class="font-mono font-bold text-zcmc-forest">${env.id}</span>
                            <span class="text-[10px] text-slate-500">&bull; ${env.origin_facility}</span>
                        </div>
                        <span class="font-bold text-[9px] text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-300">AES-256 SEALED</span>
                    </div>
                    <div>
                        <span class="text-[10px] text-slate-400 uppercase font-semibold block mb-0.5">Raw Ciphertext on Device Storage:</span>
                        <div class="font-mono text-[10px] bg-slate-900 text-emerald-400 p-2.5 rounded-lg break-all select-all max-h-20 overflow-y-auto leading-relaxed">
                            ${env.ciphertext}
                        </div>
                    </div>
                    <div class="flex items-center justify-between text-[10px] text-slate-500 pt-1">
                        <span>IV: <span class="font-mono text-slate-700">${env.iv}</span></span>
                        <span>Stored: ${new Date(env.timestamp).toLocaleTimeString()}</span>
                    </div>
                `;
                container.appendChild(card);
            });
        }

        modal.classList.remove("hidden");
        modal.classList.add("flex");
    }

    function closeVaultModal() {
        const modal = document.getElementById("zcmcVaultModal");
        if (modal) {
            modal.classList.add("hidden");
            modal.classList.remove("flex");
        }
    }

    // Unified Layout Components Injection
    function renderLayout(activePage = 'referrals') {
        // 1. Toast Container
        if (!document.getElementById("zcmcToastContainer")) {
            const tc = document.createElement("div");
            tc.id = "zcmcToastContainer";
            tc.className = "fixed top-3 left-4 right-4 z-50 flex flex-col gap-2 max-w-md mx-auto pointer-events-none";
            document.body.prepend(tc);
        }

        // 2. Desktop Institutional Sidebar
        const sidebarMount = document.getElementById("zcmcSidebarMount");
        if (sidebarMount) {
            sidebarMount.innerHTML = `
                <aside class="w-64 bg-zcmc-forest text-white border-r-2 border-zcmc-gold/60 h-screen sticky top-0 flex-shrink-0 z-30 flex flex-col justify-between shadow-xl">
                    <div class="flex flex-col">
                        <!-- Brand Seal & Motto -->
                        <div class="p-5 border-b border-white/10 flex flex-col gap-2.5">
                            <div class="flex items-center gap-3">
                                <div class="relative w-9 h-9 flex-shrink-0 flex items-center justify-center bg-zcmc-forest rounded-lg border border-zcmc-mint/40 shadow-xs">
                                    <div class="absolute w-6 h-6 border border-zcmc-gold rounded translate-x-0.5 translate-y-0.5 opacity-90"></div>
                                    <div class="relative w-6 h-6 bg-zcmc-emerald border border-zcmc-mint rounded flex items-center justify-center text-white font-bold text-xs">
                                        <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
                                            <path d="M19 10.5h-5.5V5a1.5 1.5 0 0 0-3 0v5.5H5a1.5 1.5 0 0 0 0 3h5.5V19a1.5 1.5 0 0 0 3 0v-5.5H19a1.5 1.5 0 0 0 0-3z"/>
                                        </svg>
                                    </div>
                                </div>
                                <div>
                                    <h1 class="text-sm font-extrabold tracking-wide font-heading">ZCMC HEALTH</h1>
                                    <span class="text-[9px] font-bold px-1.5 py-0.2 rounded bg-zcmc-gold/20 text-zcmc-gold border border-zcmc-gold/40 uppercase">
                                        ZAMBASULTA
                                    </span>
                                </div>
                            </div>
                            <p class="text-[10px] text-zcmc-mint font-formal italic leading-tight">
                                Care &bull; Commitment &bull; Compassion
                            </p>
                            <div class="text-[10px] text-slate-300 bg-white/5 px-2.5 py-1.5 rounded-md border border-white/10 mt-1 flex items-center justify-between">
                                <span>Edge Hub</span>
                                <span class="font-bold text-zcmc-gold">CHD IX Node</span>
                            </div>
                        </div>

                        <!-- Sidebar Navigation Menu -->
                        <nav class="p-3.5 space-y-1.5 flex-grow">
                            <a href="/" class="flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-bold transition ${activePage === 'referrals' ? 'bg-zcmc-emerald text-white border border-zcmc-gold/40 shadow-xs' : 'text-slate-300 hover:text-white hover:bg-white/10'}">
                                <svg class="w-4 h-4 ${activePage === 'referrals' ? 'text-zcmc-gold' : 'text-slate-400'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
                                </svg>
                                <span>Referral Intake &amp; Triage</span>
                            </a>

                            <a href="/dock.html" class="flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-bold transition ${activePage === 'radar' ? 'bg-zcmc-emerald text-white border border-zcmc-gold/40 shadow-xs' : 'text-slate-300 hover:text-white hover:bg-white/10'}">
                                <svg class="w-4 h-4 ${activePage === 'radar' ? 'text-zcmc-gold' : 'text-slate-400'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10a1 1 0 001 1h1m8-1a1 1 0 01-1 1H9m4-1V8a1 1 0 011-1h2.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V16a1 1 0 01-1 1h-1m-6-1a1 1 0 001 1h1M5 17a2 2 0 104 0m-4 0a2 2 0 114 0m6 0a2 2 0 104 0m-4 0a2 2 0 114 0"/>
                                </svg>
                                <span>Sea Corridor Radar</span>
                            </a>

                            <a href="/analytics.html" class="flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-bold transition ${activePage === 'analytics' ? 'bg-zcmc-emerald text-white border border-zcmc-gold/40 shadow-xs' : 'text-slate-300 hover:text-white hover:bg-white/10'}">
                                <svg class="w-4 h-4 ${activePage === 'analytics' ? 'text-zcmc-gold' : 'text-slate-400'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                                </svg>
                                <span>Regional Analytics</span>
                            </a>

                            <button onclick="ZCMC.openVaultModal()" class="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-bold text-slate-300 hover:text-white hover:bg-white/10 transition touch-action">
                                <div class="flex items-center gap-3">
                                    <svg class="w-4 h-4 text-zcmc-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
                                    </svg>
                                    <span>Encrypted Vault</span>
                                </div>
                                <span class="zcmc-vault-count px-1.5 py-0.5 rounded-full bg-zcmc-gold text-zcmc-forest font-extrabold text-[10px]">0</span>
                            </button>
                        </nav>
                    </div>

                    <!-- Sidebar Edge Node Status & Simulation Panel -->
                    <div class="p-4 border-t border-white/10 bg-black/15 space-y-3">
                        <div class="flex items-center justify-between text-xs">
                            <span class="text-slate-400 text-[11px]">System Status:</span>
                            <button onclick="ZCMC.openVaultModal()" class="zcmc-connection-badge flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-950/80 border border-zcmc-mint/40 text-zcmc-mint">
                                <span class="zcmc-conn-dot w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                                <span class="zcmc-conn-text">Online Link</span>
                            </button>
                        </div>

                        <!-- Network Simulation Control -->
                        <div class="space-y-1.5">
                            <span class="text-[10px] text-slate-400 uppercase font-bold tracking-wider block">Pitch Simulation</span>
                            <div class="grid grid-cols-2 gap-1.5 bg-slate-900/80 p-1 rounded-lg border border-white/10">
                                <button onclick="ZCMC.setSimulatedNetwork(true)" class="sim-online-btn px-2 py-1 rounded text-[10px] font-bold bg-emerald-600 text-white transition text-center">
                                    Live Link
                                </button>
                                <button onclick="ZCMC.setSimulatedNetwork(false)" class="sim-offline-btn px-2 py-1 rounded text-[10px] font-bold text-slate-300 hover:bg-slate-800 transition text-center">
                                    Island Outage
                                </button>
                            </div>
                        </div>

                        <!-- Forward Outbox Button -->
                        <button onclick="ZCMC.flushOfflineQueue()" class="w-full py-2 px-3 rounded-lg bg-zcmc-emerald hover:bg-zcmc-mint text-white text-xs font-bold transition flex items-center justify-center gap-2 border border-white/15 touch-action">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                            </svg>
                            <span>Forward Outbox</span>
                            <span class="zcmc-vault-count px-1.5 py-0.2 rounded-full bg-zcmc-gold text-zcmc-forest font-extrabold text-[10px]">0</span>
                        </button>
                    </div>
                </aside>
            `;
        }

        // 3. Mobile Header & Simulation Strip
        const mobileHeaderMount = document.getElementById("zcmcMobileHeaderMount");
        if (mobileHeaderMount) {
            mobileHeaderMount.innerHTML = `
                <header class="md:hidden sticky top-0 z-40 bg-zcmc-forest text-white border-b-2 border-zcmc-gold shadow-md">
                    <div class="px-4 py-2.5 flex items-center justify-between gap-3">
                        <div class="flex items-center gap-2.5 min-w-0">
                            <div class="relative w-8 h-8 flex-shrink-0 flex items-center justify-center bg-zcmc-forest rounded-md border border-zcmc-mint/40 shadow-xs">
                                <div class="absolute w-5 h-5 border border-zcmc-gold rounded-xs translate-x-0.5 translate-y-0.5 opacity-90"></div>
                                <div class="relative w-5 h-5 bg-zcmc-emerald border border-zcmc-mint rounded-xs flex items-center justify-center text-white font-bold text-xs">
                                    <svg class="w-3.5 h-3.5 text-white" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M19 10.5h-5.5V5a1.5 1.5 0 0 0-3 0v5.5H5a1.5 1.5 0 0 0 0 3h5.5V19a1.5 1.5 0 0 0 3 0v-5.5H19a1.5 1.5 0 0 0 0-3z"/>
                                    </svg>
                                </div>
                            </div>
                            <div class="min-w-0">
                                <div class="flex items-center gap-1.5">
                                    <h1 class="text-xs sm:text-sm font-bold tracking-tight text-white font-heading truncate">ZCMC HEALTH</h1>
                                    <span class="text-[9px] font-bold px-1.5 py-0.2 rounded bg-zcmc-gold/20 text-zcmc-gold border border-zcmc-gold/40 uppercase">ZAMBASULTA</span>
                                </div>
                                <p class="text-[10px] text-zcmc-mint font-formal italic truncate">Care &bull; Commitment &bull; Compassion</p>
                            </div>
                        </div>

                        <div class="flex items-center gap-2 flex-shrink-0">
                            <button onclick="ZCMC.openVaultModal()" class="zcmc-connection-badge flex items-center gap-1.5 px-2 py-1 rounded-full text-[11px] font-semibold bg-emerald-950/80 border border-zcmc-mint/40 text-zcmc-mint touch-action">
                                <span class="zcmc-conn-dot w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                                <span class="zcmc-conn-text text-[10px]">Online</span>
                            </button>

                            <button onclick="ZCMC.flushOfflineQueue()" class="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-bold bg-zcmc-emerald text-white border border-white/20 touch-action">
                                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                                </svg>
                                <span class="zcmc-vault-count px-1.5 py-0.2 rounded-full bg-zcmc-gold text-zcmc-forest font-extrabold text-[10px]">0</span>
                            </button>
                        </div>
                    </div>

                    <!-- Mobile Simulation Strip -->
                    <div class="bg-slate-900 text-white px-4 py-1.5 text-xs flex items-center justify-between border-t border-white/10">
                        <span class="text-slate-400 text-[10px]">Simulate Island Network:</span>
                        <div class="flex items-center gap-1">
                            <button onclick="ZCMC.setSimulatedNetwork(true)" class="sim-online-btn px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-600 text-white transition">
                                Live Link
                            </button>
                            <button onclick="ZCMC.setSimulatedNetwork(false)" class="sim-offline-btn px-2 py-0.5 rounded text-[10px] font-bold text-slate-300 hover:bg-slate-800 transition">
                                Island Outage
                            </button>
                        </div>
                    </div>
                </header>

                <!-- Offline Alert Banner -->
                <div id="zcmcOfflineNotice" class="hidden bg-amber-50 border-b border-amber-200 px-4 py-2 text-xs text-amber-900 flex items-center justify-between gap-2">
                    <div class="flex items-center gap-2">
                        <svg class="w-4 h-4 text-amber-700 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
                        </svg>
                        <span class="text-[11px] leading-tight">
                            <strong>Offline Store-and-Forward:</strong> Patient PII is sealed with <strong>AES-256</strong> on this device until internet is restored.
                        </span>
                    </div>
                    <button onclick="ZCMC.setSimulatedNetwork(true)" class="text-[11px] font-bold text-amber-800 underline flex-shrink-0">
                        Reconnect
                    </button>
                </div>
            `;
        }

        // 4. Mobile Bottom Navigation Bar
        const bottomNavMount = document.getElementById("zcmcBottomNavMount");
        if (bottomNavMount) {
            bottomNavMount.innerHTML = `
                <nav class="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-zcmc-forest text-white border-t-2 border-zcmc-gold/60 shadow-2xl flex items-center justify-around px-2 py-1.5">
                    <a href="/" class="flex flex-col items-center justify-center p-1.5 min-w-[56px] ${activePage === 'referrals' ? 'text-zcmc-gold' : 'text-slate-300 hover:text-white'} touch-action">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 4v16m8-8H4"/>
                        </svg>
                        <span class="text-[10px] font-bold mt-0.5">Referrals</span>
                    </a>

                    <a href="/dock.html" class="flex flex-col items-center justify-center p-1.5 min-w-[56px] ${activePage === 'radar' ? 'text-zcmc-gold' : 'text-slate-300 hover:text-white'} touch-action">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10a1 1 0 001 1h1m8-1a1 1 0 01-1 1H9m4-1V8a1 1 0 011-1h2.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V16a1 1 0 01-1 1h-1m-6-1a1 1 0 001 1h1M5 17a2 2 0 104 0m-4 0a2 2 0 114 0m6 0a2 2 0 104 0m-4 0a2 2 0 114 0"/>
                        </svg>
                        <span class="text-[10px] font-bold mt-0.5">Radar</span>
                    </a>

                    <a href="/analytics.html" class="flex flex-col items-center justify-center p-1.5 min-w-[56px] ${activePage === 'analytics' ? 'text-zcmc-gold' : 'text-slate-300 hover:text-white'} touch-action">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                        </svg>
                        <span class="text-[10px] font-bold mt-0.5">Stats</span>
                    </a>

                    <button onclick="ZCMC.openVaultModal()" class="flex flex-col items-center justify-center p-1.5 min-w-[56px] text-slate-300 hover:text-white touch-action relative">
                        <svg class="w-5 h-5 text-zcmc-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
                        </svg>
                        <span class="text-[10px] font-semibold mt-0.5">Vault</span>
                        <span class="zcmc-vault-indicator-dot absolute top-1 right-2 w-2 h-2 rounded-full bg-amber-400 hidden"></span>
                    </button>
                </nav>
            `;
        }

        // 5. Desktop Institutional Footer
        const footerMount = document.getElementById("zcmcFooterMount");
        if (footerMount) {
            footerMount.innerHTML = `
                <footer class="mt-auto border-t border-zcmc-border bg-white/70 py-4 px-6 text-xs text-zcmc-textMuted hidden md:block">
                    <div class="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
                        <div class="flex items-center gap-2">
                            <span class="font-bold text-zcmc-forest font-heading">Zamboanga City Medical Center (ZCMC)</span>
                            <span>&bull;</span>
                            <span class="font-formal italic">ZAMBASULTA Regional Inter-Facility Health Exchange</span>
                        </div>
                        <div class="text-[11px] text-slate-500">
                            Republic of the Philippines &bull; DOH Center for Health Development Region IX &bull; HL7 FHIR R4 Compliant
                        </div>
                    </div>
                </footer>
            `;
        }

        // 6. Device Vault Modal
        if (!document.getElementById("zcmcVaultModal")) {
            const vm = document.createElement("div");
            vm.id = "zcmcVaultModal";
            vm.className = "fixed inset-0 z-50 bg-slate-900/70 backdrop-blur-xs hidden items-end sm:items-center justify-center p-0 sm:p-4";
            vm.innerHTML = `
                <div class="bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl max-w-2xl w-full border border-slate-300 overflow-hidden flex flex-col max-h-[90vh]">
                    <div class="bg-zcmc-forest text-white px-4 py-3 flex items-center justify-between border-b-2 border-zcmc-gold">
                        <div class="flex items-center gap-2">
                            <svg class="w-5 h-5 text-zcmc-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
                            </svg>
                            <h3 class="font-bold text-xs sm:text-sm font-heading">Edge Device Encrypted Vault (AES-GCM-256)</h3>
                        </div>
                        <button onclick="ZCMC.closeVaultModal()" class="text-slate-300 hover:text-white p-1 rounded-md text-lg leading-none">&times;</button>
                    </div>

                    <div class="p-3 bg-amber-50 border-b border-amber-200 text-xs text-amber-900 flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="w-2 h-2 rounded-full bg-amber-500 animate-ping"></span>
                            <span class="text-[11px]">Store-and-Forward Outbox: Sealed patient referrals queueing on device</span>
                        </div>
                        <span class="zcmc-vault-count font-extrabold px-2 py-0.5 rounded bg-amber-200 text-amber-900 text-xs">0</span>
                    </div>

                    <div id="zcmcVaultModalContent" class="p-4 overflow-y-auto flex-grow space-y-3 bg-slate-50 max-h-[60vh]"></div>

                    <div class="px-4 py-3 bg-white border-t border-slate-200 flex items-center justify-between">
                        <span class="text-[10px] text-slate-500">Key: PBKDF2 (100k iters) &bull; SHA-256</span>
                        <div class="flex items-center gap-2">
                            <button onclick="ZCMC.closeVaultModal()" class="px-3 py-1.5 text-xs font-semibold rounded-lg text-slate-600 hover:bg-slate-100 touch-action">
                                Close
                            </button>
                            <button onclick="ZCMC.flushOfflineQueue()" class="px-3 py-1.5 text-xs font-bold rounded-lg bg-zcmc-emerald hover:bg-zcmc-mint text-white touch-action flex items-center gap-1.5">
                                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                                </svg>
                                <span>Forward All Outbox</span>
                            </button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(vm);
        }

        updateOnlineStatusUI();
        updateAllBadges();
    }

    // Hardware network listeners
    window.addEventListener('online', () => {
        isHardwareOnline = true;
        updateOnlineStatusUI();
        flushOfflineQueue();
    });
    window.addEventListener('offline', () => {
        isHardwareOnline = false;
        updateOnlineStatusUI();
    });

    // Expose public API
    window.ZCMC = {
        init: renderLayout,
        showToast,
        openVaultModal,
        closeVaultModal,
        setSimulatedNetwork,
        isEffectiveOnline,
        encryptPayload,
        decryptPayload,
        getVault: getEncryptedVault,
        saveVault: saveEncryptedVault,
        flushOfflineQueue,
        updateBadges: updateAllBadges,
        onSync: fn => syncListeners.push(fn)
    };

})(window);
