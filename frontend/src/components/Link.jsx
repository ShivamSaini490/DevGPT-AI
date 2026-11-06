// In-app link: real <a href> (so new-tab / copy-link work), client-side on plain click.
export default function Link({ to, onNavigate, children, ...props }) {
  return (
    <a
      href={to}
      onClick={(event) => {
        if (event.defaultPrevented || event.button !== 0) return;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        onNavigate(to);
      }}
      {...props}
    >
      {children}
    </a>
  );
}
