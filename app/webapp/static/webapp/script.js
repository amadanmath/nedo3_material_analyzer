(() => {
  const newBadgeInterval = 5 * 1000;
  const newBadge = document.getElementById('new_count');
  const urls = JSON.parse(document.getElementById('urls').textContent);
  function refreshNewBadge() {
    fetch(urls.new_count_text, {
    })
    .then(response => response.text())
    .then(newBadgeText => {
      newBadge.textContent = newBadgeText;
      setTimeout(refreshNewBadge, newBadgeInterval);
    });
  }
  setTimeout(refreshNewBadge, newBadgeInterval);
})();
