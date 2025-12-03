import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";

const Header = () => {
  const navItems = [
    { label: "Dashboard", active: false },
    { label: "Mapa da arborização", active: false },
    { label: "Seletor de espécies", active: true },
    { label: "Adoção de árvores", active: false },
  ];

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-[70px] bg-card border-b border-border">
      <div className="h-full max-w-[1600px] mx-auto px-6 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-8">
          <h1 className="text-2xl font-bold text-primary">VerdeFica</h1>

          {/* Search */}
          <div className="relative w-80">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Buscar árvores, espécies, bairros..."
              className="pl-10 bg-secondary/50 border-border focus:bg-card"
            />
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex items-center gap-8">
          {navItems.map((item) => (
            <a
              key={item.label}
              href="#"
              className={`text-sm font-medium transition-colors pb-1 ${
                item.active
                  ? "nav-active text-primary"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {item.label}
            </a>
          ))}
        </nav>
      </div>
    </header>
  );
};

export default Header;
