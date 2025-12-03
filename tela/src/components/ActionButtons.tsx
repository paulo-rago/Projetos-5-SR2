import { Button } from "@/components/ui/button";
import { TrendingUp, Download, FileText } from "lucide-react";

const ActionButtons = () => {
  return (
    <div className="flex flex-wrap gap-3">
      <Button
        variant="outline"
        className="border-border text-muted-foreground hover:bg-secondary hover:text-foreground"
      >
        <TrendingUp className="h-4 w-4 mr-2" />
        Ver espécies mais plantadas no Recife
      </Button>
      <Button
        variant="outline"
        className="border-border text-muted-foreground hover:bg-secondary hover:text-foreground"
      >
        <Download className="h-4 w-4 mr-2" />
        Exportar lista de espécies
      </Button>
      <Button
        variant="outline"
        className="border-border text-muted-foreground hover:bg-secondary hover:text-foreground"
      >
        <FileText className="h-4 w-4 mr-2" />
        Baixar ficha técnica completa
      </Button>
    </div>
  );
};

export default ActionButtons;
