import { Button } from "@/components/ui/button";

interface SpeciesCardProps {
  name: string;
  scientificName: string;
  badge: "Nativa" | "Frutífera";
  size: string;
  height: string;
  canopy: string;
  tags: string[];
  stock: number;
  limitedStock?: boolean;
  imageUrl: string;
}

const SpeciesCard = ({
  name,
  scientificName,
  badge,
  size,
  height,
  canopy,
  tags,
  stock,
  limitedStock,
  imageUrl,
}: SpeciesCardProps) => {
  return (
    <div className="card-elevated overflow-hidden group hover:shadow-card-hover transition-shadow duration-300 animate-fade-in">
      {/* Image */}
      <div className="relative h-44 overflow-hidden">
        <img
          src={imageUrl}
          alt={name}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
        />
      </div>

      {/* Content */}
      <div className="p-4">
        {/* Name and Badge */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div>
            <h3 className="font-semibold text-foreground">{name}</h3>
            <p className="text-sm text-muted-foreground italic">{scientificName}</p>
          </div>
          <span className={badge === "Nativa" ? "badge-native" : "badge-fruit"}>
            {badge}
          </span>
        </div>

        {/* Attributes */}
        <div className="space-y-1.5 mb-3 text-sm">
          <div className="flex justify-between">
            <span className="font-medium text-foreground">Porte:</span>
            <span className="text-muted-foreground">{size}</span>
          </div>
          <div className="flex justify-between">
            <span className="font-medium text-foreground">Altura:</span>
            <span className="text-muted-foreground">{height}</span>
          </div>
          <div className="flex justify-between">
            <span className="font-medium text-foreground">Copa:</span>
            <span className="text-muted-foreground">{canopy}</span>
          </div>
        </div>

        {/* Tags */}
        <div className="flex flex-wrap gap-1.5 mb-3">
          {tags.map((tag) => (
            <span key={tag} className="tag-chip">
              {tag}
            </span>
          ))}
        </div>

        {/* Stock */}
        <p className={`text-sm mb-4 ${limitedStock ? "stock-limited" : "text-muted-foreground"}`}>
          {limitedStock
            ? `Estoque limitado (${stock} mudas)`
            : `${stock} mudas disponíveis`}
        </p>

        {/* Buttons */}
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            className="flex-1 border-border text-muted-foreground hover:bg-secondary"
          >
            Ver detalhes
          </Button>
          <Button
            size="sm"
            className="flex-1 bg-primary hover:bg-primary/90 text-primary-foreground"
          >
            Adicionar ao plano
          </Button>
        </div>
      </div>
    </div>
  );
};

export default SpeciesCard;
