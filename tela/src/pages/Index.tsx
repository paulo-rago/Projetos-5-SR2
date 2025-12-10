import { useState, useMemo } from "react";
import FiltersPanel from "@/components/FiltersPanel";
import SpeciesCard from "@/components/SpeciesCard";
import ComparisonTable from "@/components/ComparisonTable";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { mockSpecies } from "@/data/mockData";

type SortOption = "relevance" | "name" | "stock";

interface Filters {
  search: string;
  categories: string[];
  sizes: string[];
  recommendations: string[];
  conditions: string[];
}

const Index = () => {
  const [filters, setFilters] = useState<Filters>({
    search: "",
    categories: [],
    sizes: [],
    recommendations: [],
    conditions: [],
  });
  const [sortBy, setSortBy] = useState<SortOption>("relevance");
  const [selectedSpecies, setSelectedSpecies] = useState<string[]>([]);

  // Filtrar espécies baseado nos filtros
  const filteredSpecies = useMemo(() => {
    let filtered = [...mockSpecies];

    // Filtro de busca
    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      filtered = filtered.filter(
        (species) =>
          species.name.toLowerCase().includes(searchLower) ||
          species.scientificName.toLowerCase().includes(searchLower)
      );
    }

    // Filtro de categorias
    if (filters.categories.length > 0) {
      filtered = filtered.filter((species) =>
        filters.categories.includes(species.badge)
      );
    }

    // Filtro de tamanhos
    if (filters.sizes.length > 0) {
      const sizeMap: Record<string, string> = {
        "Pequeno porte": "Pequeno",
        "Médio porte": "Médio",
        "Grande porte": "Grande",
      };
      const mappedSizes = filters.sizes.map((s) => sizeMap[s] || s);
      filtered = filtered.filter((species) =>
        mappedSizes.includes(species.size)
      );
    }

    // Filtro de recomendações (tags)
    if (filters.recommendations.length > 0) {
      filtered = filtered.filter((species) =>
        filters.recommendations.some((rec) => species.tags.includes(rec))
      );
    }

    // Filtro de condições ambientais
    if (filters.conditions.length > 0) {
      filtered = filtered.filter((species) => {
        if (filters.conditions.includes("Resistência ao sol pleno")) {
          if (!species.sunResistance) return false;
        }
        if (filters.conditions.includes("Resistência a alagamentos")) {
          if (!species.floodResistance) return false;
        }
        if (filters.conditions.includes("Baixa manutenção")) {
          if (!species.lowMaintenance) return false;
        }
        return true;
      });
    }

    return filtered;
  }, [filters]);

  // Ordenar espécies
  const sortedSpecies = useMemo(() => {
    const sorted = [...filteredSpecies];
    switch (sortBy) {
      case "name":
        return sorted.sort((a, b) => a.name.localeCompare(b.name));
      case "stock":
        return sorted.sort((a, b) => b.stock - a.stock);
      case "relevance":
      default:
        // Ordenar por relevância (estoque + popularidade)
        return sorted.sort((a, b) => {
          const scoreA = a.stock + (a.limitedStock ? -50 : 0);
          const scoreB = b.stock + (b.limitedStock ? -50 : 0);
          return scoreB - scoreA;
        });
    }
  }, [filteredSpecies, sortBy]);

  const handleToggleSpecies = (speciesId: string) => {
    setSelectedSpecies((prev) =>
      prev.includes(speciesId)
        ? prev.filter((id) => id !== speciesId)
        : [...prev, speciesId]
    );
  };

  const selectedSpeciesData = useMemo(() => {
    return sortedSpecies.filter((s) => selectedSpecies.includes(s.id));
  }, [sortedSpecies, selectedSpecies]);

  return (
    <div className="min-h-screen bg-background">
      {/* Main Content */}
      <main className="pt-8 pb-8">
        <div className="max-w-[1600px] mx-auto px-6">
          {/* Title Section */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-foreground mb-2">
              Seletor de espécies
            </h1>
            <p className="text-muted-foreground max-w-3xl">
              Explore espécies adequadas para arborização urbana do Recife. Compare
              características, encontre recomendações e visualize disponibilidade
              para plantio.
            </p>
          </div>

          {/* Two Column Layout */}
          <div className="flex gap-6">
            {/* Left Column - Filters */}
            <aside className="w-72 flex-shrink-0">
              <FiltersPanel
                filters={filters}
                onFiltersChange={setFilters}
              />
            </aside>

            {/* Right Column - Main Content */}
            <div className="flex-1 space-y-6">
              {/* Species List Header */}
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-foreground">
                  Espécies encontradas ({sortedSpecies.length})
                </h2>
                <Select
                  value={sortBy}
                  onValueChange={(value) => setSortBy(value as SortOption)}
                >
                  <SelectTrigger className="w-52 bg-card border-border">
                    <SelectValue placeholder="Ordenar por" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="relevance">Ordenar por relevância</SelectItem>
                    <SelectItem value="name">Ordenar por nome</SelectItem>
                    <SelectItem value="stock">Ordenar por estoque</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Species Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                {sortedSpecies.map((species, index) => (
                  <div
                    key={species.id}
                    style={{ animationDelay: `${index * 100}ms` }}
                  >
                    <SpeciesCard
                      {...species}
                      isSelected={selectedSpecies.includes(species.id)}
                      onToggleSelect={() => handleToggleSpecies(species.id)}
                    />
                  </div>
                ))}
              </div>

              {/* Comparison Table */}
              {selectedSpeciesData.length > 0 && (
                <ComparisonTable species={selectedSpeciesData} />
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Index;
