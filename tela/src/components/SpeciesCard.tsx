import { Button } from "@/components/ui/button";
import { BadgeType } from "@/data/mockData";

interface SpeciesCardProps {
  name: string;
  scientificName: string;
  badge: BadgeType;
  size: string;
  height: string;
  canopy: string;
  tags: string[];
  stock: number;
  limitedStock?: boolean;
  imageUrl: string;
  isSelected?: boolean;
  onToggleSelect?: () => void;
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
  isSelected = false,
  onToggleSelect,
}: SpeciesCardProps) => {
  return (
    <div
      className={`card-elevated overflow-hidden group hover:shadow-card-hover transition-shadow duration-300 animate-fade-in ${
        isSelected ? "ring-2 ring-primary" : ""
      }`}
    >
      {/* Image */}
      <div className="relative h-44 overflow-hidden">
        <img
          src={imageUrl}
          alt={name}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
        />
        {isSelected && (
          <div className="absolute top-2 right-2 w-6 h-6 bg-primary rounded-full flex items-center justify-center">
            <span className="text-white text-xs">✓</span>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-4">
        {/* Name and Badge */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div>
            <h3 className="font-semibold text-foreground">{name}</h3>
            <p className="text-sm text-muted-foreground italic">{scientificName}</p>
          </div>
          <span
            className={
              badge === "Nativa"
                ? "badge-native"
                : badge === "Frutífera"
                ? "badge-fruit"
                : badge === "Exótica"
                ? "px-2 py-1 rounded-full text-xs font-medium bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400"
                : "px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400"
            }
          >
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

        {/* Button */}
        <Button
          size="sm"
          className={`w-full ${
            isSelected
              ? "bg-secondary hover:bg-secondary/90 text-secondary-foreground"
              : "bg-primary hover:bg-primary/90 text-primary-foreground"
          }`}
          onClick={onToggleSelect}
        >
          {isSelected ? "Remover" : "Comparar"}
        </Button>
      </div>
    </div>
  );
};

export default SpeciesCard;
