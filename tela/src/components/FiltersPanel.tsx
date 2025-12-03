import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";

const FiltersPanel = () => {
  const categories = ["Nativa", "Exótica", "Frutífera", "Ornamental"];
  const sizes = ["Pequeno porte", "Médio porte", "Grande porte"];
  const recommendations = ["Ruas estreitas", "Avenidas", "Praças", "Áreas escolares"];
  const conditions = ["Resistência ao sol pleno", "Resistência a alagamentos", "Baixa manutenção"];

  return (
    <div className="card-elevated p-5 sticky top-[90px]">
      <h2 className="text-lg font-semibold text-foreground mb-5">Filtros de seleção</h2>

      {/* Search */}
      <div className="mb-6">
        <Input
          type="text"
          placeholder="Nome da espécie..."
          className="bg-secondary/30 border-border"
        />
      </div>

      {/* Categoria */}
      <FilterSection title="Categoria" items={categories} />

      {/* Porte */}
      <FilterSection title="Porte da Árvore" items={sizes} />

      {/* Recomendado para */}
      <FilterSection title="Recomendado para" items={recommendations} />

      {/* Condições */}
      <FilterSection title="Condições Ambientais" items={conditions} />

      {/* Buttons */}
      <div className="mt-6 space-y-3">
        <Button className="w-full bg-primary hover:bg-primary/90 text-primary-foreground">
          Aplicar filtros
        </Button>
        <Button variant="outline" className="w-full border-border text-muted-foreground hover:bg-secondary">
          Limpar filtros
        </Button>
      </div>
    </div>
  );
};

const FilterSection = ({ title, items }: { title: string; items: string[] }) => (
  <div className="mb-5">
    <h3 className="text-sm font-semibold text-foreground mb-3">{title}</h3>
    <div className="space-y-2.5">
      {items.map((item) => (
        <label key={item} className="flex items-center gap-2.5 cursor-pointer group">
          <Checkbox className="border-border data-[state=checked]:bg-primary data-[state=checked]:border-primary" />
          <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors">
            {item}
          </span>
        </label>
      ))}
    </div>
  </div>
);

export default FiltersPanel;
