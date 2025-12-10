import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";

interface Filters {
  search: string;
  categories: string[];
  sizes: string[];
  recommendations: string[];
  conditions: string[];
}

interface FiltersPanelProps {
  filters: Filters;
  onFiltersChange: (filters: Filters) => void;
}

const FiltersPanel = ({ filters, onFiltersChange }: FiltersPanelProps) => {
  const categories = ["Nativa", "Exótica", "Frutífera", "Ornamental"];
  const sizes = ["Pequeno porte", "Médio porte", "Grande porte"];
  const recommendations = ["Ruas estreitas", "Avenidas", "Praças", "Áreas escolares"];
  const conditions = ["Resistência ao sol pleno", "Resistência a alagamentos", "Baixa manutenção"];

  const handleSearchChange = (value: string) => {
    onFiltersChange({ ...filters, search: value });
  };

  const handleFilterToggle = (
    filterType: keyof Filters,
    value: string
  ) => {
    const currentFilters = filters[filterType] as string[];
    const newFilters = currentFilters.includes(value)
      ? currentFilters.filter((f) => f !== value)
      : [...currentFilters, value];
    onFiltersChange({ ...filters, [filterType]: newFilters });
  };

  const handleClearFilters = () => {
    onFiltersChange({
      search: "",
      categories: [],
      sizes: [],
      recommendations: [],
      conditions: [],
    });
  };

  return (
    <div className="card-elevated p-5 sticky top-[90px]">
      <h2 className="text-lg font-semibold text-foreground mb-5">Filtros de seleção</h2>

      {/* Search */}
      <div className="mb-6">
        <Input
          type="text"
          placeholder="Nome da espécie..."
          className="bg-secondary/30 border-border"
          value={filters.search}
          onChange={(e) => handleSearchChange(e.target.value)}
        />
      </div>

      {/* Categoria */}
      <FilterSection
        title="Categoria"
        items={categories}
        selectedItems={filters.categories}
        onToggle={(item) => handleFilterToggle("categories", item)}
      />

      {/* Porte */}
      <FilterSection
        title="Porte da Árvore"
        items={sizes}
        selectedItems={filters.sizes}
        onToggle={(item) => handleFilterToggle("sizes", item)}
      />

      {/* Recomendado para */}
      <FilterSection
        title="Recomendado para"
        items={recommendations}
        selectedItems={filters.recommendations}
        onToggle={(item) => handleFilterToggle("recommendations", item)}
      />

      {/* Condições */}
      <FilterSection
        title="Condições Ambientais"
        items={conditions}
        selectedItems={filters.conditions}
        onToggle={(item) => handleFilterToggle("conditions", item)}
      />

      {/* Buttons */}
      <div className="mt-6 space-y-3">
        <Button
          variant="outline"
          className="w-full border-border text-muted-foreground hover:bg-secondary"
          onClick={handleClearFilters}
        >
          Limpar filtros
        </Button>
      </div>
    </div>
  );
};

interface FilterSectionProps {
  title: string;
  items: string[];
  selectedItems: string[];
  onToggle: (item: string) => void;
}

const FilterSection = ({
  title,
  items,
  selectedItems,
  onToggle,
}: FilterSectionProps) => (
  <div className="mb-5">
    <h3 className="text-sm font-semibold text-foreground mb-3">{title}</h3>
    <div className="space-y-2.5">
      {items.map((item) => (
        <label
          key={item}
          className="flex items-center gap-2.5 cursor-pointer group"
        >
          <Checkbox
            checked={selectedItems.includes(item)}
            onCheckedChange={() => onToggle(item)}
            className="border-border data-[state=checked]:bg-primary data-[state=checked]:border-primary"
          />
          <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors">
            {item}
          </span>
        </label>
      ))}
    </div>
  </div>
);

export default FiltersPanel;
