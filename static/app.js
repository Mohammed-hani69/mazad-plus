/* ============================================
   Mazad Plus - Dashboard JavaScript
   ============================================ */

document.addEventListener('DOMContentLoaded', function () {

  'use strict';

  // ============================================
  // DOM Elements
  // ============================================
  const sidebar = document.getElementById('sidebar');
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebarClose = document.getElementById('sidebarClose');
  const sidebarOverlay = document.getElementById('sidebarOverlay');
  const mainContent = document.getElementById('mainContent');
  const statsTabs = document.getElementById('statsTabs');
  const navLinks = document.querySelectorAll('.nav-link');

  // ============================================
  // Sidebar Toggle
  // ============================================
  function openSidebar() {
    sidebar.classList.add('open');
    sidebarOverlay.classList.add('show');
    document.body.style.overflow = 'hidden';
  }

  function closeSidebar() {
    sidebar.classList.remove('open');
    sidebarOverlay.classList.remove('show');
    document.body.style.overflow = '';
  }

  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', function (e) {
      e.stopPropagation();
      if (sidebar.classList.contains('open')) {
        closeSidebar();
      } else {
        openSidebar();
      }
    });
  }

  if (sidebarClose) {
    sidebarClose.addEventListener('click', closeSidebar);
  }

  if (sidebarOverlay) {
    sidebarOverlay.addEventListener('click', closeSidebar);
  }

  // Close sidebar on Escape key
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && sidebar.classList.contains('open')) {
      closeSidebar();
    }
  });

  // Handle sidebar link clicks - close on mobile, follow link
  navLinks.forEach(function (link) {
    link.addEventListener('click', function (e) {
      // Allow normal navigation if href is valid
      const href = this.getAttribute('href');
      if (href && href !== '#' && !href.startsWith('javascript:')) {
        // Close sidebar on mobile before navigating
        if (window.innerWidth < 1200) {
          closeSidebar();
        }
        return; // Let the browser follow the link
      }

      // For # links, just toggle active
      e.preventDefault();
      navLinks.forEach(function (l) { l.classList.remove('active'); });
      this.classList.add('active');

      if (window.innerWidth < 1200) {
        closeSidebar();
      }
    });
  });

  // ============================================
  // Statistics Tabs
  // ============================================
  if (statsTabs) {
    const tabs = statsTabs.querySelectorAll('.stats-tab');

    function activateTab(tabName) {
      // Remove active from all tabs
      tabs.forEach(function (t) { t.classList.remove('active'); });

      // Add active to matching tab
      tabs.forEach(function (t) {
        if (t.getAttribute('data-tab') === tabName) {
          t.classList.add('active');
        }
      });

      // Show/hide data-section sections
      const sections = document.querySelectorAll('[data-section]');
      sections.forEach(function (section) {
        const allowed = section.getAttribute('data-section').split(' ');
        if (tabName === 'overview' || allowed.includes(tabName)) {
          section.style.display = '';
        } else {
          section.style.display = 'none';
        }
      });

      // Show/hide tab-panel-content sections
      const tabPanels = document.querySelectorAll('.tab-panel-content');
      tabPanels.forEach(function (panel) {
        const panelTab = panel.getAttribute('data-tab-content');
        if (tabName === 'overview' || panelTab === tabName) {
          panel.style.display = '';
        } else {
          panel.style.display = 'none';
        }
      });
    }

    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        const tabName = this.getAttribute('data-tab');
        activateTab(tabName);

        // Scroll to content
        const firstVisible = document.querySelector('[data-section]:not([style*="display: none"]), .tab-panel-content:not([style*="display: none"])');
        if (firstVisible) {
          firstVisible.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        document.dispatchEvent(new CustomEvent('tabChanged', {
          detail: { tab: tabName }
        }));
      });
    });
  }

  // ============================================
  // Notification Bell
  // ============================================
  const notifBtn = document.getElementById('notifBtn');
  if (notifBtn) {
    notifBtn.addEventListener('click', function () {
      // Toggle notification panel (placeholder)
      this.classList.toggle('active');
    });
  }

  // ============================================
  // Window Resize Handler
  // ============================================
  let resizeTimer;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      // Auto-close sidebar on desktop when resizing up
      if (window.innerWidth >= 1200 && sidebar.classList.contains('open')) {
        closeSidebar();
      }
    }, 250);
  });

  // ============================================
  // Chart Bars Animation
  // ============================================
  function animateChartBars() {
    const bars = document.querySelectorAll('.chart-bar');
    bars.forEach(function (bar, index) {
      bar.style.animationDelay = (index * 0.05) + 's';
    });
  }
  animateChartBars();

  // ============================================
  // Stats Counter Animation
  // ============================================
  function animateCounters() {
    const counters = document.querySelectorAll('.stat-number');
    const speed = 50;

    counters.forEach(function (counter) {
      const targetText = counter.textContent;
      const target = parseInt(targetText.replace(/[^0-9]/g, ''));
      if (isNaN(target)) return;

      const suffix = targetText.replace(/[0-9]/g, '');
      let count = 0;
      const increment = Math.ceil(target / 30);

      function updateCount() {
        count += increment;
        if (count > target) {
          count = target;
        }
        counter.textContent = count.toLocaleString() + suffix;
        if (count < target) {
          requestAnimationFrame(updateCount);
        }
      }
      updateCount();
    });
  }

  // Intersection Observer for counter animation
  const cardsSection = document.getElementById('dashboardCards');
  if (cardsSection && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            animateCounters();
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.2 }
    );
    observer.observe(cardsSection);
  } else {
    // Fallback: animate immediately
    setTimeout(animateCounters, 500);
  }

  // ============================================
  // Sidebar Search (filter menu items)
  // ============================================
  const sidebarSearch = document.getElementById('sidebarSearchInput') ||
                        document.querySelector('.sidebar-search .form-control');
  if (sidebarSearch) {
    sidebarSearch.addEventListener('input', function () {
      const query = this.value.toLowerCase().trim();
      const sections = document.querySelectorAll('.sidebar-nav .nav-section');

      sections.forEach(function (section) {
        const items = section.querySelectorAll('.nav-link');
        let hasVisible = false;

        items.forEach(function (item) {
          const text = item.querySelector('.nav-text')
            ? item.querySelector('.nav-text').textContent.toLowerCase()
            : '';

          if (!query || text.includes(query)) {
            item.style.display = 'flex';
            hasVisible = true;
          } else {
            item.style.display = 'none';
          }
        });

        const title = section.querySelector('.nav-section-title');
        if (title) {
          title.style.display = hasVisible ? 'block' : 'none';
        }
      });
    });
  }

  // ============================================
  // Keyboard Shortcuts
  // ============================================
  document.addEventListener('keydown', function (e) {
    // Ctrl + B -> Toggle sidebar
    if (e.ctrlKey && e.key === 'b') {
      e.preventDefault();
      if (sidebar.classList.contains('open') || window.innerWidth < 1200) {
        if (sidebar.classList.contains('open')) {
          closeSidebar();
        } else {
          openSidebar();
        }
      }
    }

    // / -> Focus search
    if (e.key === '/' && !['INPUT', 'TEXTAREA'].includes(e.target.tagName)) {
      e.preventDefault();
      const searchInput = document.querySelector('.navbar-search .form-control') ||
                         document.querySelector('.sidebar-search .form-control');
      if (searchInput) searchInput.focus();
    }
  });

  // ============================================
  // Tooltip / Hover Helpers
  // ============================================
  // Add data-title to nav items for tooltip effect on collapsed sidebar
  navLinks.forEach(function (link) {
    const text = link.querySelector('.nav-text');
    if (text) {
      link.setAttribute('data-title', text.textContent);
    }
  });

  // ============================================
  // Help Icons (Bootstrap Popovers)
  // ============================================
  const helpIcons = document.querySelectorAll('.help-icon');
  helpIcons.forEach(function (icon) {
    new bootstrap.Popover(icon, {
      trigger: 'click',
      html: true,
      sanitize: false,
      placement: 'auto',
    });

    // Close on Escape
    icon.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        const pop = bootstrap.Popover.getInstance(icon);
        if (pop) pop.hide();
      }
    });
  });

  // Close popover when clicking outside
  document.addEventListener('click', function (e) {
    if (!e.target.closest('.help-icon') && !e.target.closest('.popover')) {
      helpIcons.forEach(function (icon) {
        const pop = bootstrap.Popover.getInstance(icon);
        if (pop) pop.hide();
      });
    }
  });

  // ============================================
  // Console Branding
  // ============================================
  console.log('%c Mazad Plus v1.0.0 ',
    'background: #4f46e5; color: white; font-size: 14px; font-weight: bold; padding: 8px 12px; border-radius: 4px;'
  );
  console.log('%c Dashboard Loaded Successfully ',
    'background: #10b981; color: white; font-size: 12px; padding: 4px 8px; border-radius: 4px;'
  );

  // ============================================
  // Notification System
  // ============================================
  var notifBadge = document.getElementById('notifBadge');
  var notifList = document.getElementById('notifList');
  var notifMarkAll = document.getElementById('notifMarkAll');

  function fetchNotifCount() {
    if (!notifBadge) return;
    fetch('/api/notifications/count')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.unread > 0) {
          notifBadge.style.display = '';
          notifBadge.textContent = data.unread > 99 ? '99+' : data.unread;
        } else {
          notifBadge.style.display = 'none';
        }
      })
      .catch(function() {});
  }

  function fetchNotifications() {
    if (!notifList) return;
    notifList.innerHTML = '<div class="notif-loading text-center py-3"><div class="spinner-border spinner-border-sm text-primary" role="status"></div><small class="d-block mt-1 text-muted">جاري التحميل...</small></div>';
    fetch('/api/notifications?page=1')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (!data.notifications || data.notifications.length === 0) {
          notifList.innerHTML = '<div class="notif-empty"><i class="far fa-bell-slash"></i><span>لا توجد إشعارات</span></div>';
          return;
        }
        var html = '';
        data.notifications.forEach(function(n) {
          var iconMap = { info: 'fa-info-circle', warning: 'fa-exclamation-triangle', success: 'fa-check-circle', danger: 'fa-times-circle' };
          var icon = iconMap[n.type] || 'fa-info-circle';
          var unreadClass = n.is_read ? '' : ' unread';
          var msgHtml = n.message ? '<span class="notif-message">' + n.message + '</span>' : '';
          var linkHtml = n.link ? '<a href="' + n.link + '" class="notif-title">' + n.title + '</a>' : '<span class="notif-title">' + n.title + '</span>';
          html += '<div class="notif-item' + unreadClass + '" data-id="' + n.id + '">';
          html += '<div class="notif-icon ' + n.type + '"><i class="fas ' + icon + '"></i></div>';
          html += '<div class="notif-body">' + linkHtml + msgHtml + '<span class="notif-time">' + n.time_ago + '</span></div>';
          html += '</div>';
        });
        notifList.innerHTML = html;

        // Mark as read on click
        notifList.querySelectorAll('.notif-item').forEach(function(item) {
          item.addEventListener('click', function() {
            var id = this.dataset.id;
            if (!id) return;
            fetch('/api/notifications/' + id + '/read', { method: 'POST', headers: { 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '' } })
              .then(function(r) { return r.json(); })
              .then(function() {
                item.classList.remove('unread');
                fetchNotifCount();
              })
              .catch(function() {});
          });
        });
      })
      .catch(function() {
        notifList.innerHTML = '<div class="notif-empty"><i class="fas fa-exclamation-circle"></i><span>فشل تحميل الإشعارات</span></div>';
      });
  }

  // Mark all as read
  if (notifMarkAll) {
    notifMarkAll.addEventListener('click', function(e) {
      e.preventDefault();
      fetch('/api/notifications/read-all', { method: 'POST', headers: { 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '' } })
        .then(function(r) { return r.json(); })
        .then(function() {
          notifList.querySelectorAll('.notif-item.unread').forEach(function(el) { el.classList.remove('unread'); });
          fetchNotifCount();
        })
        .catch(function() {});
    });
  }

  // View all link — only for super admins
  var notifViewAll = document.getElementById('notifViewAll');
  if (notifViewAll) {
    if (currentUserIsSuperAdmin) {
      notifViewAll.addEventListener('click', function(e) {
        e.preventDefault();
        window.location.href = '/admin/notifications';
      });
    } else {
      notifViewAll.style.display = 'none';
    }
  }

  // Poll unread count every 30 seconds
  fetchNotifCount();
  setInterval(fetchNotifCount, 30000);

  // When dropdown is shown, load notifications
  var notifDropdown = document.getElementById('notificationDropdown');
  if (notifDropdown) {
    notifDropdown.addEventListener('shown.bs.dropdown', function() {
      fetchNotifications();
    });
  }

  // Simple CSRF helper for fetch
  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  var csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

  // ============================================
  // Dark Mode
  // ============================================
  var darkToggle = document.getElementById('darkModeToggle');
  var htmlEl = document.documentElement;
  var storedTheme = localStorage.getItem('theme');

  function applyTheme(theme) {
    if (theme === 'dark') {
      htmlEl.setAttribute('data-theme', 'dark');
      if (darkToggle) darkToggle.innerHTML = '<i class="fas fa-sun"></i>';
      localStorage.setItem('theme', 'dark');
    } else {
      htmlEl.removeAttribute('data-theme');
      if (darkToggle) darkToggle.innerHTML = '<i class="fas fa-moon"></i>';
      localStorage.setItem('theme', 'light');
    }
  }

  if (storedTheme) {
    applyTheme(storedTheme);
  }

  if (darkToggle) {
    darkToggle.addEventListener('click', function() {
      var current = htmlEl.getAttribute('data-theme');
      applyTheme(current === 'dark' ? 'light' : 'dark');
      fetch('/api/toggle-dark-mode', { method: 'POST', headers: { 'X-CSRFToken': csrfToken } }).catch(function() {});
    });
  }

});