// static/wiki/js/wiki_menu.js
document.addEventListener('DOMContentLoaded', function() {
    const hamburger = document.getElementById('hamburger');
    const menu = document.getElementById('menu');
    
    // Check if menu element exists before proceeding
    if (!menu) {
        // console.warn("Menu element not found for wiki_menu.js");
        return;
    }

    const menuConfigSlug = menu.dataset.menuConfigSlug || "default-menu-config-slug"; // Get from data attribute
    let allWikiPagesData = [];
    try {
        const pagesDataScript = document.getElementById('allWikiPagesJsonData');
        if (pagesDataScript) {
            allWikiPagesData = JSON.parse(pagesDataScript.textContent);
        } else {
            // console.warn("allWikiPagesJsonData script tag not found.");
        }
    } catch (e) {
        console.error("Error parsing allWikiPagesData:", e);
    }


    const desktopBreakpoint = window.matchMedia('(min-width: 1101px)');

    function updateHamburgerActiveState() {
        if (!hamburger) return;
        if (menu.classList.contains('open') && !desktopBreakpoint.matches) {
            hamburger.classList.add('is-active');
        } else {
            hamburger.classList.remove('is-active');
        }
    }

    function handleMenuStateForResize() {
        if (desktopBreakpoint.matches) {
            menu.classList.remove('open'); // Close mobile menu on resize to desktop
            document.body.style.overflow = ''; // Ensure body scroll is re-enabled
        } else {
            // On resize to mobile, if menu was open, ensure body overflow is hidden
            if (menu.classList.contains('open')) {
                document.body.style.overflow = 'hidden';
            } else {
                document.body.style.overflow = '';
            }
        }
        updateHamburgerActiveState();
    }

    // Initial check and setup
    handleMenuStateForResize();
    desktopBreakpoint.addEventListener('change', handleMenuStateForResize);

    if (hamburger) {
        hamburger.addEventListener('click', function() {
            if (!desktopBreakpoint.matches) { // Only toggle for mobile view
                menu.classList.toggle('open');
                if (menu.classList.contains('open')) {
                    document.body.style.overflow = 'hidden'; // Prevent scrolling of page content under open menu
                } else {
                    document.body.style.overflow = ''; // Re-enable scrolling
                }
                updateHamburgerActiveState();
            }
        });
    }

    const searchInput = document.getElementById('wikiMenuSearchInput');
    const itembar = document.getElementById('itembar'); // Ul container for pinned items and dynamic results

    if (!itembar) {
        // console.warn("Itembar element not found for menu search.");
        return;
    }

    // Query for pinned items and headings within itembar to ensure correct scope
    const pinnedMenuItems = itembar.querySelectorAll('li[data-pinned-item]');
    const pinnedMenuHeadings = itembar.querySelectorAll('h3[data-section-title]');
    const dynamicSearchResultsContainer = document.getElementById('dynamicSearchResultsContainer'); // This might be outside itembar in some layouts
    const dynamicSearchResultsList = document.getElementById('dynamicSearchResultsList'); // UL for dynamic results

    if (searchInput && dynamicSearchResultsList && dynamicSearchResultsContainer) {
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase().trim();
            const visiblePinnedSlugs = new Set();

            // Filter pinned menu items
            pinnedMenuItems.forEach(item => {
                const itemText = item.textContent.toLowerCase();
                const itemSlug = item.dataset.slug; // Assuming slug is stored in data-slug
                if (itemText.includes(searchTerm)) {
                    item.style.display = '';
                    if(itemSlug) visiblePinnedSlugs.add(itemSlug);
                } else {
                    item.style.display = 'none';
                }
            });

            // Filter pinned menu section headings
            pinnedMenuHeadings.forEach(heading => {
                let nextElement = heading.nextElementSibling;
                let sectionHasVisibleItem = false;
                // Check if any subsequent pinned list items under this heading are visible
                while (nextElement && nextElement.tagName === 'LI' && nextElement.hasAttribute('data-pinned-item')) {
                    if (nextElement.style.display !== 'none') {
                        sectionHasVisibleItem = true;
                        break;
                    }
                    nextElement = nextElement.nextElementSibling;
                }

                // Also check if heading text itself matches
                const headingLink = heading.querySelector('a.section-title-link');
                const headingTextContent = headingLink ? headingLink.textContent : (heading.textContent || heading.innerText); // Get text content correctly
                const headingText = headingTextContent.toLowerCase();

                if (sectionHasVisibleItem || headingText.includes(searchTerm)) {
                    heading.style.display = '';
                } else {
                    heading.style.display = 'none';
                }
            });

            // Clear previous dynamic search results
            dynamicSearchResultsList.innerHTML = '';
            let dynamicResultsFound = false;

            if (searchTerm !== '') {
                allWikiPagesData.forEach(page => {
                    if (page.title.toLowerCase().includes(searchTerm)) {
                        // Add to dynamic results only if not already visible as a pinned item
                        if (!visiblePinnedSlugs.has(page.slug)) {
                            const li = document.createElement('li');
                            //  data-pinned-item is not added here as these are dynamic
                            const a = document.createElement('a');
                            a.href = page.url;
                            a.classList.add('link');

                            const button = document.createElement('button');
                            button.classList.add('button-transparent');

                            const circleSpan = document.createElement('span');
                            circleSpan.classList.add('circle');
                            // Optionally, add a default color or derive from page data if available
                            button.appendChild(circleSpan);

                            button.appendChild(document.createTextNode(page.title));
                            a.appendChild(button);
                            li.appendChild(a);
                            dynamicSearchResultsList.appendChild(li);
                            dynamicResultsFound = true;
                        }
                    }
                });
            }

            // Show/hide the dynamic results container
            if (dynamicResultsFound) {
                dynamicSearchResultsContainer.style.display = 'block';
            } else {
                dynamicSearchResultsContainer.style.display = 'none';
            }

            // If search term is empty, reset everything to visible
            if (searchTerm === '') {
                pinnedMenuItems.forEach(item => item.style.display = '');
                pinnedMenuHeadings.forEach(heading => heading.style.display = '');
                dynamicSearchResultsContainer.style.display = 'none';
            }
        });
    } else {
        if (!searchInput) console.warn("Search input not found.");
        if (!dynamicSearchResultsList) console.warn("Dynamic search results list not found.");
        if (!dynamicSearchResultsContainer) console.warn("Dynamic search results container not found.");
    }
});