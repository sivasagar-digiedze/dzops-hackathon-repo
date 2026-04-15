function Sidebar({ items, activePage, onPageChange }) {
  return (
    <aside className="sidebar">
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <button
              className={activePage === item.id ? "active-side" : ""}
              onClick={() => onPageChange(item.id)}
            >
              {item.label}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}

export default Sidebar;
