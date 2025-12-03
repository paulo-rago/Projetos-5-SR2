import FiltersPanel from "@/components/FiltersPanel";
import SpeciesCard from "@/components/SpeciesCard";
import ComparisonTable from "@/components/ComparisonTable";
import RecommendationsCard from "@/components/RecommendationsCard";
import ActionButtons from "@/components/ActionButtons";
import Footer from "@/components/Footer";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const speciesData = [
  {
    name: "Ipê Amarelo",
    scientificName: "Handroanthus albus",
    badge: "Nativa" as const,
    size: "Médio",
    height: "8–15m",
    canopy: "25–40m²",
    tags: ["Avenidas", "Praças"],
    stock: 320,
    imageUrl: "https://images.unsplash.com/photo-1518495973542-4542c06a5843?w=400&h=300&fit=crop",
  },
  {
    name: "Mangueira",
    scientificName: "Mangifera indica",
    badge: "Frutífera" as const,
    size: "Grande",
    height: "15–30m",
    canopy: "80–120m²",
    tags: ["Praças"],
    stock: 156,
    imageUrl: "https://images.unsplash.com/photo-1509316975850-ff9c5deb0cd9?w=400&h=300&fit=crop",
  },
  {
    name: "Pau-Brasil",
    scientificName: "Caesalpinia echinata",
    badge: "Nativa" as const,
    size: "Médio",
    height: "10–15m",
    canopy: "15–25m²",
    tags: ["Avenidas", "Escolas"],
    stock: 12,
    limitedStock: true,
    imageUrl: "https://images.unsplash.com/photo-1513836279014-a89f7a76ae86?w=400&h=300&fit=crop",
  },
  {
    name: "Craibeira",
    scientificName: "Tabebuia aurea",
    badge: "Nativa" as const,
    size: "Pequeno",
    height: "4–8m",
    canopy: "8–15m²",
    tags: ["Ruas estreitas", "Escolas"],
    stock: 89,
    imageUrl: "https://images.unsplash.com/photo-1502082553048-f009c37129b9?w=400&h=300&fit=crop",
  },
];

const Index = () => {
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
              <FiltersPanel />
            </aside>

            {/* Right Column - Main Content */}
            <div className="flex-1 space-y-6">
              {/* Species List Header */}
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-foreground">
                  Espécies encontradas (24)
                </h2>
                <Select defaultValue="relevance">
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
                {speciesData.map((species, index) => (
                  <div
                    key={species.name}
                    style={{ animationDelay: `${index * 100}ms` }}
                  >
                    <SpeciesCard {...species} />
                  </div>
                ))}
              </div>

              {/* Comparison Table */}
              <ComparisonTable />

              {/* Recommendations */}
              <RecommendationsCard />

              {/* Action Buttons */}
              <ActionButtons />
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
};

export default Index;
