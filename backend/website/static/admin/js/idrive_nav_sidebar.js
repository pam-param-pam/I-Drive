(() => {
    const sidebar = document.getElementById("nav-sidebar");
    if (!sidebar) return;

    const storageKey = "idrive.admin.navSidebarScrollTop";
    const savedPosition = Number(sessionStorage.getItem(storageKey));
    if (Number.isFinite(savedPosition) && savedPosition > 0) {
        sidebar.scrollTop = savedPosition;
    }

    const savePosition = () => sessionStorage.setItem(storageKey, String(sidebar.scrollTop));
    sidebar.addEventListener("scroll", savePosition, { passive: true });
    sidebar.addEventListener("click", (event) => {
        if (event.target.closest("a")) savePosition();
    }, true);
})();
