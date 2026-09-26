// ============================================================
// DROPDOWN
// ============================================================

function toggleDropdown(id) {
    const el = document.getElementById(id);

    if (!el) return;

    const wasOpen = el.classList.contains("open");

    document.querySelectorAll(".dropdown.open").forEach(function (dropdown) {
        dropdown.classList.remove("open");
    });

    if (!wasOpen) {
        el.classList.add("open");
    }
}


document.addEventListener("click", function (event) {
    document.querySelectorAll(".dropdown.open").forEach(function (dropdown) {

        if (!dropdown.contains(event.target)) {
            dropdown.classList.remove("open");
        }

    });
});


// ============================================================
// TOAST
// ============================================================

function showToast(message, type = "default") {

    let wrap = document.getElementById("toastWrap");

    if (!wrap) {
        wrap = document.createElement("div");
        wrap.id = "toastWrap";
        wrap.className = "toast-wrap";

        document.body.appendChild(wrap);
    }

    const toast = document.createElement("div");

    toast.className = `toast ${type}`;
    toast.textContent = message;

    wrap.appendChild(toast);

    requestAnimationFrame(function () {
        toast.classList.add("show");
    });

    setTimeout(function () {

        toast.classList.remove("show");

        setTimeout(function () {
            toast.remove();
        }, 250);

    }, 3500);
}


// ============================================================
// API POST HELPER
// ============================================================

async function apiPost(url, data, isFormData = false) {

    const opts = {
        method: "POST"
    };

    if (isFormData) {

        opts.body = data;

    } else {

        opts.headers = {
            "Content-Type": "application/json"
        };

        opts.body = JSON.stringify(data || {});
    }

    try {

        const res = await fetch(url, opts);

        return await res.json();

    } catch (error) {

        console.error("API request failed:", error);

        return {
            ok: false,
            error: "Unable to connect to the server."
        };
    }
}


// ============================================================
// ACTIVE NAVIGATION
// ============================================================

document.addEventListener("DOMContentLoaded", function () {

    const currentPath = window.location.pathname;

    document.querySelectorAll(".nav-links a").forEach(function (link) {

        const href = link.getAttribute("href");

        if (!href) return;

        if (href === currentPath) {
            link.classList.add("active");
        }

    });

});


// ============================================================
// SMOOTH ANCHOR SCROLL
// ============================================================

document.addEventListener("click", function (event) {

    const link = event.target.closest('a[href^="#"]');

    if (!link) return;

    const targetId = link.getAttribute("href");

    if (!targetId || targetId === "#") return;

    const target = document.querySelector(targetId);

    if (!target) return;

    event.preventDefault();

    target.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });

});


// ============================================================
// PAGE LOAD
// ============================================================

window.addEventListener("load", function () {

    document.body.classList.add("page-loaded");

});